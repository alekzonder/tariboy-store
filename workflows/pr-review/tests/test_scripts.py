#!/usr/bin/env python3
"""Contracts for the pr-review workflow's source and check scripts.

Each script runs as a subprocess with the daemon's script protocol: a result
file, state directories, the quiet and reject exit codes and, for checks, a
task snapshot in TARIBOY_TASK_FILE. A local HTTP server thread stands in for
the GitHub API (GITHUB_API_URL points at it; the scripts still use curl).
"""

import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

WORKFLOW_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = WORKFLOW_DIR / "scripts"
OPEN_PULLS = SCRIPTS / "open-pulls.py"
REVIEW_CHECK = SCRIPTS / "review-check.py"
PUBLISHED_CHECK = SCRIPTS / "published-check.py"
TOKEN = "ghp_test-secret-token-0123456789"
QUIET = 111
REJECT = 112
PR_URL = "https://github.com/acme/widget/pull/42"
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
REVIEW_URL = PR_URL + "#pullrequestreview-9001"
PATCH = "@@ -10,3 +10,4 @@ def run():\n     a = 1\n-    b = 2\n+    b = 3\n+    c = 4\n     return a\n"

sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True

import review_lib  # noqa: E402


class FakeGitHub:
    """Routes map a request path (without its query) to (status, body)."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(
                    {"path": self.path, "authorization": self.headers.get("Authorization")}
                )
                status, body = owner.routes.get(self.path.split("?", 1)[0], (404, {"message": "Not Found"}))
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()


def pull(number=42, head=HEAD_SHA, draft=False, title="Add c"):
    return {
        "number": number,
        "state": "open",
        "draft": draft,
        "title": title,
        "user": {"login": "octo"},
        "head": {"sha": head, "ref": "feature"},
        "base": {"ref": "main"},
    }


def task(outcome="findings", artifacts=None):
    return {
        "key": "REV-ab12",
        "queue": "REV",
        "title": "Review acme/widget#42: Add c",
        "description": "Review it.",
        "customer": "user:alice",
        "status": "review",
        "outcome": outcome,
        "visit": {"id": 3, "entered_at": "2026-10-07T10:00:00Z"},
        "artifacts": [
            {"name": name, "value": value, "author": "agent:rev-1", "created_at": "2026-10-07T10:01:00Z"}
            for name, value in (artifacts or {}).items()
        ],
        "workflow": {"name": "pr-review", "version": "0.1.0", "digest": "sha256:" + "0" * 64},
    }


def comments(*items, body="One problem."):
    return json.dumps({"body": body, "comments": list(items)})


class ScriptCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, *, snapshot=None, env=None, outcome=None, token=True):
        run_dir = Path(tempfile.mkdtemp(dir=self.root, prefix="run-"))
        result_file = run_dir / "result.json"
        full_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TARIBOY_RESULT_FILE": str(result_file),
            "TARIBOY_QUIET_EXIT": str(QUIET),
            "TARIBOY_REJECT_EXIT": str(REJECT),
        }
        if snapshot is not None:
            task_file = run_dir / "task.json"
            task_file.write_text(json.dumps(snapshot), encoding="utf-8")
            full_env["TARIBOY_TASK_FILE"] = str(task_file)
            full_env["TARIBOY_TASK_DIR"] = str(self.state)
        else:
            full_env["TARIBOY_SOURCE_DIR"] = str(self.state)
        if outcome:
            full_env["TARIBOY_WORKFLOW_OUTCOME"] = outcome
        if token:
            full_env["GH_TOKEN"] = TOKEN
        full_env.update(env or {})
        completed = subprocess.run(
            [str(script)],
            cwd=str(self.state),
            env=full_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw = result_file.read_text(encoding="utf-8") if result_file.exists() else ""
        for label, text in (("result file", raw), ("stdout", completed.stdout), ("stderr", completed.stderr)):
            self.assertNotIn(TOKEN, text, f"token leaked into the {label}")
        return completed.returncode, (json.loads(raw) if raw else None), completed.stderr


class OpenPullsTests(ScriptCase):
    def run_source(self, github, repositories="acme/widget,acme/gadget", **kwargs):
        env = {"GITHUB_API_URL": github.url, "REVIEW_REPOSITORIES": repositories}
        return self.run_script(OPEN_PULLS, env=env, **kwargs)

    def test_one_item_per_open_non_draft_pull_request(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(42), pull(7, draft=True), pull(3)])
            github.routes["/repos/acme/gadget/pulls"] = (200, [pull(5, title="Fix\nbuild")])
            code, result, stderr = self.run_source(github)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(set(result), {"items"})
        self.assertEqual(
            [item["key"] for item in result["items"]],
            ["acme/widget#3", "acme/widget#42", "acme/gadget#5"],
        )
        item = result["items"][1]
        self.assertEqual(set(item), {"key", "title", "description", "artifacts"})
        self.assertEqual(item["title"], "Review acme/widget#42: Add c")
        self.assertEqual(item["artifacts"], {"pull_request": PR_URL})
        self.assertIn("untrusted", item["description"])
        self.assertEqual(result["items"][2]["title"], "Review acme/gadget#5: Fix build")
        self.assertTrue(all(r["authorization"] == f"Bearer {TOKEN}" for r in github.requests))
        self.assertTrue(all("state=open" in r["path"] for r in github.requests))

    def test_no_open_pull_request_is_quiet(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(7, draft=True)])
            github.routes["/repos/acme/gadget/pulls"] = (200, [])
            code, result, _ = self.run_source(github)
        self.assertEqual((code, result), (QUIET, None))

    def test_separators_and_duplicates(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(42)])
            code, result, stderr = self.run_source(github, repositories=" acme/widget,\nacme/widget ")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(github.requests), 1)
        self.assertEqual([item["key"] for item in result["items"]], ["acme/widget#42"])

    def test_invalid_repositories_fail_without_calling_github(self):
        for value in ("", " , ", "acme", "acme/widget/extra", "acme/../x", "acme/wid get"):
            with self.subTest(value=value), FakeGitHub() as github:
                code, result, stderr = self.run_source(github, repositories=value)
                self.assertEqual(code, 1)
                self.assertIsNone(result)
                self.assertIn("REVIEW_REPOSITORIES", stderr)
                self.assertEqual(github.requests, [])

    def test_a_single_repository_without_separator_names_the_fix(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(42)])
            code, result, stderr = self.run_source(github, repositories="acme/widget")
            self.assertEqual((code, result), (1, None))
            self.assertIn("owner/repo,", stderr)
            code, result, stderr = self.run_source(github, repositories="acme/widget,")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["items"][0]["key"], "acme/widget#42")

    def test_more_than_fifty_rotates_unreported_keys_first(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(n) for n in range(1, 71)])
            code, first, stderr = self.run_source(github, repositories="acme/widget,")
            self.assertEqual(code, 0, stderr)
            code, second, stderr = self.run_source(github, repositories="acme/widget,")
            self.assertEqual(code, 0, stderr)
        first_keys = [item["key"] for item in first["items"]]
        second_keys = [item["key"] for item in second["items"]]
        self.assertEqual(len(first_keys), 50)
        self.assertEqual(first_keys[0], "acme/widget#1")
        self.assertEqual(second_keys[:20], [f"acme/widget#{n}" for n in range(51, 71)])
        self.assertEqual(len(second_keys), 50)
        state = json.loads((self.state / "reported.json").read_text())
        self.assertEqual(len(state), 70)

    def test_state_forgets_closed_pull_requests(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(1), pull(2)])
            self.run_source(github, repositories="acme/widget,")
            github.routes["/repos/acme/widget/pulls"] = (200, [pull(2)])
            self.run_source(github, repositories="acme/widget,")
        self.assertEqual(set(json.loads((self.state / "reported.json").read_text())), {"acme/widget#2"})

    def test_github_errors_fail_without_a_result(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls"] = (500, {"message": TOKEN})
            code, result, stderr = self.run_source(github, repositories="acme/widget,")
        self.assertEqual((code, result), (1, None))
        self.assertIn("HTTP 500", stderr)

    def test_missing_token_fails(self):
        with FakeGitHub() as github:
            code, result, stderr = self.run_source(github, token=False)
        self.assertEqual((code, result), (1, None))
        self.assertIn("GH_TOKEN", stderr)


class ReviewCheckTests(ScriptCase):
    def run_check(self, github, outcome="findings", **artifacts):
        values = {"pull_request": PR_URL, "head_sha": HEAD_SHA, "review": "## Review\n\nOne problem."}
        values.update(artifacts)
        values = {k: v for k, v in values.items() if v is not None}
        return self.run_script(
            REVIEW_CHECK,
            snapshot=task(outcome, values),
            outcome=outcome,
            env={"GITHUB_API_URL": github.url},
        )

    def route(self, github, head=HEAD_SHA, files=None):
        github.routes["/repos/acme/widget/pulls/42"] = (200, pull(head=head))
        github.routes["/repos/acme/widget/pulls/42/files"] = (
            200,
            files if files is not None else [{"filename": "app.py", "patch": PATCH}],
        )

    def test_findings_on_diff_lines_pass(self):
        with FakeGitHub() as github:
            self.route(github)
            code, result, stderr = self.run_check(
                github,
                review_comments=comments(
                    {"path": "app.py", "line": 11, "body": "b changed"},
                    {"path": "app.py", "line": 11, "side": "LEFT", "body": "old b"},
                    {"path": "app.py", "start_line": 10, "line": 12, "body": "range"},
                ),
            )
        self.assertEqual(code, 0, stderr)
        self.assertIn("3 inline comments", result["message"])

    def test_findings_with_body_only_pass(self):
        with FakeGitHub() as github:
            self.route(github)
            code, _, stderr = self.run_check(github, review_comments=comments())
        self.assertEqual(code, 0, stderr)
        self.assertNotIn("/files", " ".join(r["path"] for r in github.requests))

    def test_no_findings_needs_no_comments(self):
        with FakeGitHub() as github:
            self.route(github)
            code, _, stderr = self.run_check(github, outcome="no_findings")
        self.assertEqual(code, 0, stderr)

    def test_moved_head_rejects(self):
        for outcome in ("findings", "no_findings"):
            with self.subTest(outcome=outcome), FakeGitHub() as github:
                self.route(github, head=OTHER_SHA)
                code, result, _ = self.run_check(github, outcome, review_comments=comments())
                self.assertEqual(code, REJECT)
                self.assertIn(OTHER_SHA, result["message"])

    def test_lines_outside_the_diff_reject(self):
        with FakeGitHub() as github:
            self.route(github, files=[{"filename": "app.py", "patch": PATCH}, {"filename": "logo.png"}])
            code, result, _ = self.run_check(
                github,
                review_comments=comments(
                    {"path": "app.py", "line": 40, "body": "far"},
                    {"path": "other.py", "line": 1, "body": "unchanged"},
                    {"path": "logo.png", "line": 1, "body": "binary"},
                    {"path": "app.py", "line": 13, "side": "LEFT", "body": "added line"},
                ),
            )
        self.assertEqual(code, REJECT)
        message = result["message"]
        self.assertIn("comment 1: line 40 of app.py", message)
        self.assertIn("comment 2: the pull request does not change other.py", message)
        self.assertIn("comment 3: GitHub shows no diff for logo.png", message)
        self.assertIn("comment 4: line 13 of app.py (LEFT)", message)

    def test_malformed_artifacts_reject_without_calling_github(self):
        cases = {
            "pull_request": {"pull_request": "https://gitlab.com/acme/widget/-/merge_requests/1"},
            "head_sha": {"head_sha": HEAD_SHA[:12]},
            "review": {"review": "  "},
            "json": {"review_comments": "{"},
            "missing": {"review_comments": None},
            "body": {"review_comments": comments(body="")},
            "extra": {"review_comments": json.dumps({"body": "x", "event": "APPROVE"})},
            "line": {"review_comments": comments({"path": "app.py", "line": 0, "body": "x"})},
            "side": {"review_comments": comments({"path": "app.py", "line": 1, "side": "BOTH", "body": "x"})},
            "range": {"review_comments": comments({"path": "app.py", "start_line": 5, "line": 5, "body": "x"})},
        }
        for label, artifacts in cases.items():
            with self.subTest(label), FakeGitHub() as github:
                values = {"review_comments": comments()}
                values.update(artifacts)
                code, result, _ = self.run_check(github, **values)
                self.assertEqual(code, REJECT)
                self.assertTrue(result["message"])
                self.assertEqual(github.requests, [])

    def test_github_failure_is_a_failure(self):
        with FakeGitHub() as github:
            github.routes["/repos/acme/widget/pulls/42"] = (502, {})
            code, result, _ = self.run_check(github, review_comments=comments())
        self.assertEqual(code, 1)
        self.assertEqual(set(result), {"message"})


class PublishedCheckTests(ScriptCase):
    def run_check(self, github, **artifacts):
        values = {
            "pull_request": PR_URL,
            "head_sha": HEAD_SHA,
            "review_comments": comments({"path": "app.py", "line": 11, "body": "b"}),
            "published_review": REVIEW_URL,
        }
        values.update(artifacts)
        return self.run_script(
            PUBLISHED_CHECK, snapshot=task("published", values), env={"GITHUB_API_URL": github.url}
        )

    def route(self, github, state="COMMENTED", commit=HEAD_SHA, count=1):
        github.routes["/repos/acme/widget/pulls/42/reviews/9001"] = (
            200,
            {"id": 9001, "state": state, "commit_id": commit},
        )
        github.routes["/repos/acme/widget/pulls/42/reviews/9001/comments"] = (
            200,
            [{"id": n} for n in range(count)],
        )

    def test_published_review_passes(self):
        with FakeGitHub() as github:
            self.route(github)
            code, result, stderr = self.run_check(github)
        self.assertEqual(code, 0, stderr)
        self.assertIn("9001", result["message"])

    def test_bad_url_rejects_without_calling_github(self):
        for value in ("", PR_URL, PR_URL + "#pullrequestreview-x", "https://github.com/acme/other/pull/42#pullrequestreview-1"):
            with self.subTest(value=value), FakeGitHub() as github:
                code, _, _ = self.run_check(github, published_review=value)
                self.assertEqual(code, REJECT)
                self.assertEqual(github.requests, [])

    def test_missing_pending_wrong_commit_and_missing_comments_reject(self):
        for label, kwargs in {
            "pending": {"state": "PENDING"},
            "commit": {"commit": OTHER_SHA},
            "comments": {"count": 0},
        }.items():
            with self.subTest(label), FakeGitHub() as github:
                self.route(github, **kwargs)
                code, _, _ = self.run_check(github)
                self.assertEqual(code, REJECT)
        with FakeGitHub() as github:
            code, result, _ = self.run_check(github)
        self.assertEqual(code, REJECT)
        self.assertIn("does not exist", result["message"])


class DiffLinesTests(unittest.TestCase):
    def test_sides_follow_the_hunk(self):
        lines = review_lib.diff_lines(PATCH)
        self.assertEqual(lines["RIGHT"], {10, 11, 12, 13})
        self.assertEqual(lines["LEFT"], {10, 11, 12})

    def test_no_newline_marker_and_several_hunks(self):
        patch = "@@ -1 +1 @@\n-a\n+b\n\\ No newline at end of file\n@@ -20,2 +20,2 @@\n x\n-y\n+z\n"
        lines = review_lib.diff_lines(patch)
        self.assertEqual(lines["RIGHT"], {1, 20, 21})
        self.assertEqual(lines["LEFT"], {1, 20, 21})


if __name__ == "__main__":
    unittest.main(verbosity=1)
