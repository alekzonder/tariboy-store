#!/usr/bin/env python3
"""Contracts for the development workflow's check scripts.

Each check runs as a subprocess with the daemon's script protocol: a task
snapshot in TARIBOY_TASK_FILE, a result file, a task state directory, and the
quiet and reject exit codes in the environment. A local HTTP server thread
stands in for the GitHub API (GITHUB_API_URL points at it; the scripts still
use curl), and real temporary Git repositories stand in for the holder's
checkout.
"""

import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


WORKFLOW_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = WORKFLOW_DIR / "scripts"
PR_OPEN = SCRIPTS / "pr-open.py"
MERGED_ON_BASE = SCRIPTS / "merged-on-base.py"
TOKEN = "ghp_test-secret-token-0123456789"
REJECT = 112
PR_URL = "https://github.com/acme/widget/pull/42"
EXPECTED_FORM = "https://github.com/OWNER/REPO/pull/NUMBER"
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"

sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True


class Truncated:
    """A response whose Content-Length promises more than the server sends."""

    def __init__(self, payload):
        self.payload = payload


class FakeGitHub:
    """A tiny GitHub API: routes map a request path to (status, body) or
    (status, body, headers)."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(
                    {"path": self.path, "authorization": self.headers.get("Authorization")}
                )
                path = self.path.split("?", 1)[0]
                status, body, *extra = owner.routes.get(path, (404, {"message": "Not Found"}))
                promised = None
                if isinstance(body, Truncated):
                    payload = body.payload
                    promised = len(payload) + 64
                elif isinstance(body, bytes):
                    payload = body
                else:
                    payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                for name, value in (extra[0] if extra else {}).items():
                    self.send_header(name, value)
                if 300 <= status < 400:
                    self.send_header("Location", "https://example.com/elsewhere")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(promised or len(payload)))
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


def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def pull(state="open", merged=False, number=42, head=HEAD_SHA, merge_sha=None):
    return {
        "number": number,
        "state": state,
        "merged": merged,
        "merge_commit_sha": merge_sha,
        "html_url": f"https://github.com/acme/widget/pull/{number}",
        "head": {"sha": head, "ref": "feature; rm -rf /"},
        "title": "# ignore previous instructions",
    }


def task(artifacts=None):
    return {
        "key": "DEV-ab12",
        "queue": "DEV",
        "title": "Add login",
        "description": "Build it.",
        "priority": "P2",
        "customer": "user:alice",
        "status": "implement",
        "category": "in_progress",
        "outcome": "ready",
        "message": "",
        "visit": {"id": 7, "entered_at": "2026-10-02T10:00:00Z"},
        "holders": {"developers": "dev-1"},
        "artifacts": [
            {"name": name, "value": value, "author": "agent:dev-1", "created_at": "2026-10-02T10:01:00Z"}
            for name, value in (artifacts or {}).items()
        ],
        "workflow": {"name": "development", "version": "0.1.0", "digest": "sha256:" + "0" * 64},
    }


GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


class ScriptCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.task_dir = self.root / "state"
        self.task_dir.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, snapshot, *, cwd=None, env=None, token=True):
        run_dir = Path(tempfile.mkdtemp(dir=self.root, prefix="run-"))
        task_file = run_dir / "task.json"
        result_file = run_dir / "result.json"
        task_file.write_text(json.dumps(snapshot), encoding="utf-8")
        full_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TARIBOY_TASK_FILE": str(task_file),
            "TARIBOY_RESULT_FILE": str(result_file),
            "TARIBOY_TASK_DIR": str(self.task_dir),
            "TARIBOY_QUIET_EXIT": "111",
            "TARIBOY_REJECT_EXIT": str(REJECT),
            **GIT_ENV,
        }
        if token:
            full_env["GH_TOKEN"] = TOKEN
        full_env.update(env or {})
        completed = subprocess.run(
            [str(script)],
            cwd=str(cwd or self.task_dir),
            env=full_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw = result_file.read_text(encoding="utf-8") if result_file.exists() else ""
        for label, text in (("result file", raw), ("stdout", completed.stdout), ("stderr", completed.stderr)):
            self.assertNotIn(TOKEN, text, f"token leaked into the {label}")
        result = json.loads(raw) if raw else None
        if result is not None:
            self.assertLessEqual(set(result), {"outcome", "message", "artifacts"})
        return completed.returncode, result, completed.stdout, completed.stderr

    def message(self, result):
        self.assertIsNotNone(result, "the script wrote no result file")
        return result.get("message", "")

    def failure_message(self, result, stderr):
        """A failure (exit 1) leaves its diagnostic, and only that, in the result
        file, so it reaches the request and the pause comment."""
        self.assertIsNotNone(result, "a failure writes its diagnostic to the result file")
        self.assertEqual(set(result), {"message"})
        self.assertTrue(result["message"])
        self.assertIn(result["message"], stderr)
        return result["message"]


class PullRequestOpenTests(ScriptCase):
    def setUp(self):
        super().setUp()
        self.github = FakeGitHub().__enter__()
        self.addCleanup(self.github.__exit__)

    def run_pr_open(self, artifacts=None, **kwargs):
        env = {"GITHUB_API_URL": self.github.url, **kwargs.pop("env", {})}
        return self.run_script(PR_OPEN, task(artifacts), env=env, **kwargs)

    def route(self, status, body, number=42):
        self.github.routes[f"/repos/acme/widget/pulls/{number}"] = (status, body)

    def test_missing_artifact_rejects_with_the_expected_form(self):
        code, result, _, _ = self.run_pr_open({})
        self.assertEqual(code, REJECT)
        self.assertIn(EXPECTED_FORM, self.message(result))
        self.assertEqual(self.github.requests, [])

    def test_invalid_urls_reject_without_calling_github(self):
        cases = [
            "not a url",
            "github.com/acme/widget/pull/42",
            "http://github.com/acme/widget/pull/42",
            "https://gitlab.com/acme/widget/pull/42",
            "https://github.com.evil.example/acme/widget/pull/42",
            "https://evil.example/github.com/acme/widget/pull/42",
            "https://user@github.com/acme/widget/pull/42",
            "https://github.com:443/acme/widget/pull/42",
            "https://GITHUB.COM/acme/widget/pull/42",
            "https://github.com/acme/widget/pull/42?tab=files",
            "https://github.com/acme/widget/pull/42#discussion",
            "https://github.com/acme/widget/pull/42/",
            "https://github.com/acme/widget/pull/42/files",
            "https://github.com/acme/widget/pull/042",
            "https://github.com/acme/widget/pull/0",
            "https://github.com/acme/widget/pull/-1",
            "https://github.com/acme/widget/pull/4 2",
            "https://github.com/acme/widget/pull/４２",
            "https://github.com/acme/widget/pull/42\n",
            " https://github.com/acme/widget/pull/42",
            "https://github.com/acme/widget/issues/42",
            "https://github.com/acme/widget/pulls/42",
            "https://github.com/acme/pull/42",
            "https://github.com/../widget/pull/42",
            "https://github.com/acme/./pull/42",
            "https://github.com/ac%6De/widget/pull/42",
            "https://github.com/acme/wid get/pull/42",
            "https://github.com//widget/pull/42",
        ]
        for value in cases:
            with self.subTest(value=value):
                code, result, _, _ = self.run_pr_open({"pull_request": value})
                self.assertEqual(code, REJECT)
                self.assertIn(EXPECTED_FORM, self.message(result))
        self.assertEqual(self.github.requests, [])

    def test_open_pull_request_passes_with_its_head(self):
        self.route(200, pull())
        code, result, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 0)
        self.assertEqual(
            self.message(result), "Pull request acme/widget#42 is open at 0123456789ab."
        )
        self.assertNotIn("outcome", result)
        self.assertNotIn("feature", json.dumps(result))

    def test_token_travels_only_in_the_authorization_header(self):
        self.route(200, pull())
        code, _, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 0)
        self.assertEqual(len(self.github.requests), 1)
        request = self.github.requests[0]
        self.assertEqual(request["authorization"], f"Bearer {TOKEN}")
        self.assertNotIn(TOKEN, request["path"])

    def test_github_token_is_the_fallback(self):
        self.route(200, pull())
        code, _, _, _ = self.run_pr_open(
            {"pull_request": PR_URL}, token=False, env={"GITHUB_TOKEN": TOKEN}
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.github.requests[0]["authorization"], f"Bearer {TOKEN}")

    def test_missing_pull_request_rejects(self):
        code, result, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, REJECT)
        self.assertIn("acme/widget#42", self.message(result))

    def test_closed_unmerged_pull_request_rejects(self):
        self.route(200, pull(state="closed"))
        code, result, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, REJECT)
        self.assertIn("reopen it or open a new one", self.message(result))

    def test_merged_pull_request_passes(self):
        self.route(200, pull(state="closed", merged=True, merge_sha="f" * 40))
        code, result, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 0)
        self.assertIn("merged", self.message(result))

    def test_no_token_is_a_failure(self):
        code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL}, token=False)
        self.assertEqual(code, 1)
        self.assertIn("GH_TOKEN", self.failure_message(result, stderr))
        self.assertLess(len(stderr), 2048)
        self.assertEqual(self.github.requests, [])

    def test_transport_failure_is_a_failure_without_the_token(self):
        code, result, _, stderr = self.run_pr_open(
            {"pull_request": PR_URL}, env={"GITHUB_API_URL": f"http://127.0.0.1:{unused_port()}"}
        )
        self.assertEqual(code, 1)
        self.failure_message(result, stderr)
        self.assertLess(len(stderr), 2048)

    def test_non_json_answer_is_a_failure(self):
        self.route(200, b"<html>rate limited</html>")
        code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 1)
        self.assertNotIn("rate limited", self.failure_message(result, stderr))
        self.assertNotIn("rate limited", stderr)

    def test_server_errors_are_failures(self):
        for status in (301, 401, 403, 429, 500):
            with self.subTest(status=status):
                self.route(status, {"message": "nope"})
                code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL})
                self.assertEqual(code, 1)
                self.assertIn(f"HTTP {status}", self.failure_message(result, stderr))

    def test_failure_result_carries_the_diagnostic_and_no_token(self):
        self.route(500, {"message": TOKEN})
        code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 1)
        self.assertEqual(self.failure_message(result, stderr), "GitHub answered HTTP 500")

    def test_a_truncated_body_is_a_failure(self):
        payload = json.dumps(pull()).encode("utf-8")
        self.route(200, Truncated(payload))
        code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 1)
        self.failure_message(result, stderr)

    def test_malformed_pull_request_is_a_failure(self):
        for body in (
            [],
            {**pull(), "number": 43},
            {**pull(), "state": "draft"},
            {**pull(), "merged": "no"},
            {**pull(), "head": {"sha": "not a sha"}},
        ):
            with self.subTest(body=body):
                self.route(200, body)
                code, result, _, stderr = self.run_pr_open({"pull_request": PR_URL})
                self.assertEqual(code, 1)
                self.failure_message(result, stderr)

    def test_token_echoed_by_github_never_leaves_the_script(self):
        self.route(200, {**pull(), "head": {"sha": TOKEN}})
        code, _, _, _ = self.run_pr_open({"pull_request": PR_URL})
        self.assertEqual(code, 1)

    def test_api_root_must_be_https_or_loopback(self):
        code, result, _, stderr = self.run_pr_open(
            {"pull_request": PR_URL}, env={"GITHUB_API_URL": "http://api.example.com"}
        )
        self.assertEqual(code, 1)
        self.failure_message(result, stderr)
        self.assertEqual(self.github.requests, [])


class MergedOnBaseTests(ScriptCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        self.commit("first")
        self.git("checkout", "--quiet", "-b", "feature")
        self.commit("feature work")
        self.feature_sha = self.git("rev-parse", "HEAD")
        self.git("checkout", "--quiet", "main")
        self.git("merge", "--quiet", "--no-ff", "-m", "Merge feature", "feature")
        self.merge_sha = self.git("rev-parse", "HEAD")
        self.git("branch", "--quiet", "-D", "feature")

    def git(self, *args, cwd=None):
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo),
            env={"PATH": "/usr/bin:/bin", "HOME": str(self.home), **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()

    def commit(self, message):
        path = self.repo / "file.txt"
        with path.open("a", encoding="utf-8") as output:
            output.write(message + "\n")
        self.git("add", "file.txt")
        self.git("commit", "--quiet", "-m", message)

    def write_state(self, value):
        path = self.task_dir / "pr-monitor.json"
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def run_check(self, merge_commit=None, cwd=None):
        artifacts = {} if merge_commit is None else {"merge_commit": merge_commit}
        snapshot = task(artifacts)
        snapshot["status"] = "complete"
        snapshot["outcome"] = "cleaned"
        return self.run_script(MERGED_ON_BASE, snapshot, cwd=cwd or self.repo)

    def test_clean_main_checkout_passes(self):
        self.write_state({"base_ref": "main", "head_ref": "feature"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, 0, result)

    def test_abbreviated_merge_commit_passes(self):
        code, result, _, _ = self.run_check(self.merge_sha[:7])
        self.assertEqual(code, 0, result)

    def test_missing_merge_commit_rejects(self):
        code, result, _, _ = self.run_check(None)
        self.assertEqual(code, REJECT)
        self.assertIn("merge_commit", self.message(result))

    def test_malformed_merge_commit_rejects(self):
        for value in (
            "zzzzzzz",
            self.merge_sha[:6],
            self.merge_sha + "0",
            self.merge_sha.upper(),
            "-" + self.merge_sha[:10],
            self.merge_sha + "\n",
            "HEAD",
            "main",
        ):
            with self.subTest(value=value):
                code, result, _, _ = self.run_check(value)
                self.assertEqual(code, REJECT)
                self.assertIn("merge_commit", self.message(result))

    def test_outside_a_work_tree_rejects(self):
        outside = self.root / "outside"
        outside.mkdir()
        code, result, _, _ = self.run_check(self.merge_sha, cwd=outside)
        self.assertEqual(code, REJECT)
        self.assertIn("main checkout", self.message(result))

    def test_base_branch_from_state_must_exist(self):
        self.write_state({"base_ref": "release"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, REJECT)
        self.assertIn("release", self.message(result))
        self.assertIn("does not exist", self.message(result))

    def test_base_branch_from_state_is_used(self):
        self.git("branch", "release", self.merge_sha)
        self.git("reset", "--quiet", "--hard", "HEAD~1")
        self.write_state({"base_ref": "release", "head_ref": "feature"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, 0, result)

    def test_merge_commit_not_on_base_rejects(self):
        self.git("reset", "--quiet", "--hard", "HEAD~1")
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, REJECT)
        self.assertIn("fast-forward main first", self.message(result))

    def test_unknown_merge_commit_rejects(self):
        code, result, _, _ = self.run_check("abcdef1234567")
        self.assertEqual(code, REJECT)
        self.assertIn("fast-forward main first", self.message(result))

    def test_linked_worktree_on_the_head_branch_rejects(self):
        self.git("branch", "feature", self.feature_sha)
        self.git("worktree", "add", "--quiet", str(self.root / "task-tree"), "feature")
        self.write_state({"base_ref": "main", "head_ref": "feature"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, REJECT)
        self.assertIn("worktree", self.message(result))
        self.assertNotIn("feature", self.message(result))

    def test_local_head_branch_rejects(self):
        self.git("branch", "feature", self.feature_sha)
        self.write_state({"base_ref": "main", "head_ref": "feature"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, REJECT)
        self.assertIn("local branch", self.message(result))
        self.assertNotIn("feature", self.message(result))

    def test_unknown_head_branch_skips_the_head_checks(self):
        self.git("branch", "feature", self.feature_sha)
        self.write_state({"base_ref": "main"})
        code, result, _, _ = self.run_check(self.merge_sha)
        self.assertEqual(code, 0, result)

    def test_check_from_a_subdirectory_passes(self):
        sub = self.repo / "sub"
        sub.mkdir()
        code, result, _, _ = self.run_check(self.merge_sha, cwd=sub)
        self.assertEqual(code, 0, result)

    def test_unsafe_state_values_are_failures(self):
        for state in (
            {"base_ref": "-main"},
            {"base_ref": "@{-1}"},
            {"base_ref": "main", "head_ref": "--orphan"},
            {"base_ref": "bad..name"},
            {"base_ref": 7},
            "not json",
            "[]",
        ):
            with self.subTest(state=state):
                self.write_state(state)
                code, result, _, stderr = self.run_check(self.merge_sha)
                self.assertEqual(code, 1)
                self.failure_message(result, stderr)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        import pr_lib

        self.lib = pr_lib

    def test_parse_pull_request_url(self):
        self.assertEqual(self.lib.parse_pull_request_url(PR_URL), ("acme", "widget", 42))
        self.assertEqual(
            self.lib.parse_pull_request_url("https://github.com/A-b_c.d/r.e-p_o/pull/7"),
            ("A-b_c.d", "r.e-p_o", 7),
        )
        for value in ("https://github.com/acme/widget/pull/42/", "https://github.com/acme/widget/pull/0", 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.lib.parse_pull_request_url(value)

    def test_artifact(self):
        snapshot = task({"plan": "p", "pull_request": PR_URL})
        self.assertEqual(self.lib.artifact(snapshot, "pull_request"), PR_URL)
        self.assertIsNone(self.lib.artifact(snapshot, "merge_commit"))
        self.assertIsNone(self.lib.artifact({}, "plan"))

    def test_write_result_cuts_the_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            previous = os.environ.get("TARIBOY_RESULT_FILE")
            os.environ["TARIBOY_RESULT_FILE"] = str(path)
            try:
                self.lib.write_result(message="é" * 5000)
                written = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(set(written), {"message"})
                self.assertLessEqual(len(written["message"]), 4000)
                self.assertLessEqual(len(written["message"].encode("utf-8")), 4096)
                self.assertIn("é", path.read_text(encoding="utf-8"))
                self.lib.write_result(outcome="merged", message="m", artifacts={"merge_commit": "abc1234"})
                written = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    written, {"outcome": "merged", "message": "m", "artifacts": {"merge_commit": "abc1234"}}
                )
            finally:
                if previous is None:
                    os.environ.pop("TARIBOY_RESULT_FILE", None)
                else:
                    os.environ["TARIBOY_RESULT_FILE"] = previous

    def test_exit_codes_default(self):
        self.assertEqual(self.lib.QUIET_EXIT, int(os.environ.get("TARIBOY_QUIET_EXIT", "111")))
        self.assertEqual(self.lib.REJECT_EXIT, int(os.environ.get("TARIBOY_REJECT_EXIT", "112")))


class TransientFailureTests(unittest.TestCase):
    """pr_lib.GitHubClient raises TransientFailure for what a retry can fix:
    HTTP 429, 5xx, a 403 whose x-ratelimit-remaining is 0, and the curl exits
    of a refused, reset, timed-out, or failed connection."""

    def setUp(self):
        import pr_lib

        self.lib = pr_lib
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task_dir = self.root / "state"
        self.task_dir.mkdir()
        self.github = FakeGitHub().__enter__()
        self.addCleanup(self.github.__exit__)

    def fake_curl(self, version):
        """A curl that reports `version` and logs its arguments (never the
        token: it travels in the config descriptor)."""
        path = self.root / f"curl-{version}"
        log = self.root / f"curl-{version}.log"
        path.write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = "--version" ]; then echo "curl {version} (x86_64-pc-linux-gnu)"; exit 0; fi\n'
            f'printf "%s\\n" "$@" >>"{log}"\n'
            'exec /usr/bin/curl "$@"\n',
            encoding="utf-8",
        )
        path.chmod(0o755)
        return str(path), log

    def get(self, status, headers=None, *, curl_bin=None, api=None, task_dir=True):
        self.github.routes["/repos/acme/widget/pulls/42"] = (status, {"message": "x"}, headers or {})
        env = {"GITHUB_API_URL": api or self.github.url}
        if task_dir:
            env["TARIBOY_TASK_DIR"] = str(self.task_dir)
        with mock.patch.dict(os.environ, env):
            if not task_dir:
                os.environ.pop("TARIBOY_TASK_DIR", None)
            client = self.lib.GitHubClient(token=TOKEN, curl_bin=curl_bin)
            return client.get("/repos/acme/widget/pulls/42")

    def assert_transient(self, *args, **kwargs):
        with self.assertRaises(self.lib.TransientFailure) as caught:
            self.get(*args, **kwargs)
        self.assertIsInstance(caught.exception, self.lib.ScriptFailure)
        return caught.exception

    def assert_not_transient(self, *args, **kwargs):
        with self.assertRaises(self.lib.ScriptFailure) as caught:
            self.get(*args, **kwargs)
        self.assertNotIsInstance(caught.exception, self.lib.TransientFailure)
        return caught.exception

    def test_rate_limits_and_server_errors_are_transient(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.assert_transient(status)

    def test_a_403_is_transient_only_when_the_rate_limit_is_spent(self):
        self.assert_transient(403, {"X-RateLimit-Remaining": "0"})
        for headers in ({}, {"X-RateLimit-Remaining": "17"}):
            with self.subTest(headers=headers):
                self.assert_not_transient(403, headers)

    def test_other_http_errors_are_not_transient(self):
        for status in (301, 401, 404, 422):
            with self.subTest(status=status):
                error = self.assert_not_transient(status)
                self.assertIsInstance(error, self.lib.GitHubHTTPError)
                self.assertEqual(error.status, status)

    def test_a_refused_connection_is_transient(self):
        error = self.assert_transient(200, api=f"http://127.0.0.1:{unused_port()}")
        self.assertIn("curl exit 7", str(error))

    def test_a_current_curl_reads_the_header_through_write_out(self):
        curl_bin, log = self.fake_curl("8.5.0")
        self.assert_transient(403, {"X-RateLimit-Remaining": "0"}, curl_bin=curl_bin)
        arguments = log.read_text(encoding="utf-8")
        self.assertIn("%header{x-ratelimit-remaining}", arguments)
        self.assertNotIn("--dump-header", arguments)
        self.assertEqual(list(self.task_dir.iterdir()), [])

    def test_an_old_curl_dumps_the_headers_inside_the_task_dir_and_removes_them(self):
        curl_bin, log = self.fake_curl("7.81.0")
        self.assert_transient(403, {"X-RateLimit-Remaining": "0"}, curl_bin=curl_bin)
        self.assert_not_transient(403, {"X-RateLimit-Remaining": "3"}, curl_bin=curl_bin)
        arguments = log.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("%header{x-ratelimit-remaining}", "\n".join(arguments))
        dumps = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--dump-header"]
        self.assertEqual(len(dumps), 2)
        for dump in dumps:
            self.assertEqual(Path(dump).parent, self.task_dir)
        self.assertEqual(list(self.task_dir.iterdir()), [], "the header file is removed")

    def test_an_old_curl_without_a_task_dir_cannot_tell_a_rate_limit(self):
        curl_bin, log = self.fake_curl("7.81.0")
        self.assert_not_transient(403, {"X-RateLimit-Remaining": "0"}, curl_bin=curl_bin, task_dir=False)
        self.assertNotIn("--dump-header", log.read_text(encoding="utf-8"))


class FileTests(unittest.TestCase):
    def test_every_script_is_executable(self):
        scripts = sorted(path for path in SCRIPTS.iterdir() if path.is_file())
        self.assertTrue(scripts)
        for path in scripts:
            with self.subTest(script=path.name):
                self.assertTrue(os.access(path, os.X_OK), f"{path.name} is not executable")

    def test_no_symlinks_in_the_workflow(self):
        for path in WORKFLOW_DIR.rglob("*"):
            self.assertFalse(path.is_symlink(), f"{path} is a symlink")

    def test_status_instructions_are_short(self):
        for name in ("plan", "approval", "implement", "complete"):
            with self.subTest(status=name):
                lines = (WORKFLOW_DIR / "statuses" / f"{name}.md").read_text(encoding="utf-8").splitlines()
                self.assertLess(len(lines), 60)


if __name__ == "__main__":
    if shutil.which("curl") is None or shutil.which("git") is None:
        sys.exit("curl and git are required")
    unittest.main()
