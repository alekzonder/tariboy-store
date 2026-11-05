"""Shared helpers of the image-improve script tests.

Each script runs as a subprocess with the daemon's script protocol: a task
snapshot in TARIBOY_TASK_FILE, a result file, a task state directory, and the
quiet and reject exit codes in the environment. A local HTTP server thread
stands in for the GitHub API (GITHUB_API_URL points at it).
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
TOKEN = "ghp_test-secret-token-0123456789"
REJECT = 112
QUIET = 111
PR_URL = "https://github.com/acme/widget/pull/42"
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
MERGE_SHA = "89abcdef0123456789abcdef0123456789abcdef"
BRANCH = "task/IMPROVE-ab12"
CUSTOMER = "user:alice"

sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True


class FakeGitHub:
    """A tiny GitHub API: routes map a request path to (status, body)."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                path = self.path.split("?", 1)[0]
                status, body = owner.routes.get(path, (404, {"message": "Not Found"}))
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


def pull(state="open", merged=False, head=HEAD_SHA, merge_sha=None, mergeable=True,
         closed_at=None, title="Tighten a rule", body="Adds an eval."):
    return {
        "number": 42,
        "state": state,
        "merged": merged,
        "mergeable": mergeable,
        "merge_commit_sha": merge_sha,
        "closed_at": closed_at,
        "head": {"sha": head, "ref": BRANCH},
        "base": {"ref": "main"},
        "title": title,
        "body": body,
        "user": {"login": "agent-bot"},
    }


def review(review_id, state, login="alice"):
    return {"id": review_id, "state": state, "user": {"login": login}, "body": "untrusted text", "submitted_at": "2026-11-05T10:00:00Z"}


def task(status="triage", outcome="", artifacts=None, key="IMPROVE-ab12", visit_id=7,
         entered_at="2026-11-05T10:00:00Z", rows=None):
    items = [
        {"name": name, "value": value, "author": "agent:tariboy-image-creator", "created_at": "2026-11-05T10:01:00Z"}
        for name, value in (artifacts or {}).items()
    ]
    items.extend(rows or [])
    return {
        "key": key,
        "queue": "IMPROVE",
        "title": "Improve an image",
        "description": "A finding.",
        "priority": "P2",
        "customer": CUSTOMER,
        "status": status,
        "category": "in_progress",
        "outcome": outcome,
        "message": "",
        "visit": {"id": visit_id, "entered_at": entered_at},
        "holders": {"image-creators": "tariboy-image-creator"},
        "artifacts": items,
        "workflow": {"name": "image-improve", "version": "0.1.0", "digest": "sha256:" + "0" * 64},
    }


class ScriptCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task_dir = self.root / "state"
        self.task_dir.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, snapshot, *, env=None, outcome=None, token=True):
        run_dir = Path(tempfile.mkdtemp(dir=self.root, prefix="run-"))
        task_file = run_dir / "task.json"
        result_file = run_dir / "result.json"
        task_file.write_text(json.dumps(snapshot), encoding="utf-8")
        full_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TARIBOY_TASK_FILE": str(task_file),
            "TARIBOY_RESULT_FILE": str(result_file),
            "TARIBOY_TASK_DIR": str(self.task_dir),
            "TARIBOY_QUIET_EXIT": str(QUIET),
            "TARIBOY_REJECT_EXIT": str(REJECT),
        }
        if outcome is not None:
            full_env["TARIBOY_WORKFLOW_OUTCOME"] = outcome
        if token:
            full_env["GITHUB_TOKEN"] = TOKEN
        full_env.update(env or {})
        completed = subprocess.run(
            [str(script)], cwd=str(self.task_dir), env=full_env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
        raw = result_file.read_text(encoding="utf-8") if result_file.exists() else ""
        for label, text in (("result file", raw), ("stdout", completed.stdout), ("stderr", completed.stderr)):
            self.assertNotIn(TOKEN, text, f"token leaked into the {label}")
        result = json.loads(raw) if raw else None
        if result is not None:
            self.assertLessEqual(set(result), {"outcome", "message", "artifacts"})
        return completed.returncode, result, completed.stderr

    def rejected(self, code, result, *fragments):
        self.assertEqual(code, REJECT, result)
        self.assertIsNotNone(result)
        for fragment in fragments:
            self.assertIn(fragment, result["message"])
