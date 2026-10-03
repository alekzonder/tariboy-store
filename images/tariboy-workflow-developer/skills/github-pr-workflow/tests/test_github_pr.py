#!/usr/bin/env python3
"""Black-box contracts for the github-pr-workflow utility: preflight and
ensure. Watching a pull request belongs to the task's workflow. The fake curl
process is the GitHub boundary: it proves the future utility uses an
inherited curl config descriptor for authentication and gives each test a
deterministic sequence of API responses.
"""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest


REPO = "alekzonder/tariboy"
HEAD = "tari-31-pr-workflow"
BASE = "main"
SECRET = "super-secret-token"
SKILL_DIR = Path(__file__).resolve().parents[1]
UTILITY = SKILL_DIR / "scripts" / "github-pr.py"


FAKE_CURL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
secret = os.environ["FAKE_CURL_EXPECTED_TOKEN"]
if secret in "\0".join(args):
    raise SystemExit("token appeared in curl argv")
if os.environ.get("FAKE_CURL_REQUIRE_DISABLE") == "1":
    if not (Path(os.environ["HOME"]) / ".curlrc").is_file():
        raise SystemExit("hostile curlrc fixture is missing")
    if not args or args[0] != "--disable":
        raise SystemExit("--disable was not the first curl option")
try:
    config = args[args.index("--config") + 1]
except (ValueError, IndexError) as exc:
    raise SystemExit("curl config descriptor was not supplied") from exc
if not config.startswith("/dev/fd/"):
    raise SystemExit("curl config is not an inherited descriptor")
config_text = Path(config).read_text(encoding="utf-8")
if "Authorization: Bearer " + secret not in config_text:
    raise SystemExit("authorization header was not supplied through config")
for candidate in Path(os.environ["FAKE_CURL_PROCESS_TEMP"]).rglob("*"):
    if candidate.is_file() and secret.encode("utf-8") in candidate.read_bytes():
        raise SystemExit("token materialized in the process temporary directory")

method = "GET"
for flag in ("-X", "--request"):
    if flag in args:
        method = args[args.index(flag) + 1]
body = None
for flag in ("--data", "--data-raw", "--data-binary"):
    if flag in args:
        body = json.loads(args[args.index(flag) + 1])
url = next((arg for arg in reversed(args) if arg.startswith("https://")), None)
if url is None:
    raise SystemExit("curl invocation has no HTTPS URL")
record_path = Path(os.environ["FAKE_CURL_RECORDS"])
with record_path.open("a", encoding="utf-8") as out:
    out.write(json.dumps({"method": method, "url": url, "json": body}, sort_keys=True) + "\n")

queue_path = Path(os.environ["FAKE_CURL_QUEUE"])
queue = json.loads(queue_path.read_text(encoding="utf-8"))
if not queue:
    raise SystemExit("unexpected curl request")
response = queue.pop(0)
queue_path.write_text(json.dumps(queue), encoding="utf-8")
for stream_name, output in (("stdout_bytes", sys.stdout.buffer), ("stderr_bytes", sys.stderr.buffer)):
    stream_bytes = response.get(stream_name)
    if stream_bytes is None:
        continue
    remaining = stream_bytes
    chunk = b"x" * 65536
    while remaining:
        output.write(chunk[:min(remaining, len(chunk))])
        output.flush()
        remaining -= min(remaining, len(chunk))
    Path(os.environ["FAKE_CURL_STREAM_COMPLETE"]).write_text(stream_name, encoding="utf-8")
    raise SystemExit(response.get("exit", 0))
payload = response.get("body", {})
if isinstance(payload, str):
    sys.stdout.write(payload)
else:
    sys.stdout.write(json.dumps(payload))
raise SystemExit(response.get("exit", 0))
'''


class FakeCurl:
    def __init__(self, responses, require_disable=False):
        self.responses = responses
        self.require_disable = require_disable
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.binary = self.path / "curl"
        self.queue = self.path / "queue.json"
        self.records = self.path / "records.jsonl"
        self.stream_complete = self.path / "stream-complete"

    def __enter__(self):
        self.binary.write_text(textwrap.dedent(FAKE_CURL), encoding="utf-8")
        self.binary.chmod(0o700)
        self.set_responses(self.responses)
        return self

    def __exit__(self, *_):
        self.temp.cleanup()

    def set_responses(self, responses):
        self.queue.write_text(json.dumps(responses), encoding="utf-8")
        self.stream_complete.unlink(missing_ok=True)

    def records_json(self):
        if not self.records.exists():
            return []
        return [json.loads(line) for line in self.records.read_text(encoding="utf-8").splitlines()]

    def env(self, expected_token, process_temp):
        return {
            "TARIBOY_GITHUB_CURL_BIN": str(self.binary),
            "FAKE_CURL_QUEUE": str(self.queue),
            "FAKE_CURL_RECORDS": str(self.records),
            "FAKE_CURL_EXPECTED_TOKEN": expected_token,
            "FAKE_CURL_PROCESS_TEMP": str(process_temp),
            "FAKE_CURL_REQUIRE_DISABLE": "1" if self.require_disable else "0",
            "FAKE_CURL_STREAM_COMPLETE": str(self.stream_complete),
        }


def pr(head="abc123", state="open", merged=False, merge_commit_sha=None):
    return {
        "number": 31,
        "state": state,
        "merged": merged,
        "merge_commit_sha": merge_commit_sha,
        "updated_at": "2026-08-21T12:00:00Z",
        "html_url": "https://github.com/alekzonder/tariboy/pull/31",
        "head": {"sha": head},
    }


class GitHubPRWorkflowTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        if not UTILITY.is_file():
            self.fail(f"github PR utility is missing: {UTILITY}")

    def run_utility(
        self,
        *args,
        curl,
        gh_token=SECRET,
        github_token=None,
        github_repository=None,
        origin_url=None,
        quiet_code=None,
    ):
        with tempfile.TemporaryDirectory() as process_sandbox:
            sandbox = Path(process_sandbox)
            home = sandbox / "home"
            xdg_state = sandbox / "xdg-state"
            xdg_cache = sandbox / "xdg-cache"
            xdg_config = sandbox / "xdg-config"
            xdg_data = sandbox / "xdg-data"
            xdg_runtime = sandbox / "xdg-runtime"
            process_temp = sandbox / "tmp"
            working_dir = sandbox / "cwd"
            for directory in (home, xdg_state, xdg_cache, xdg_config, xdg_data, xdg_runtime, process_temp, working_dir):
                directory.mkdir(mode=0o700)
            if origin_url is not None:
                subprocess.run(
                    ["git", "init", "--quiet"],
                    cwd=working_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "config", "remote.origin.url", origin_url],
                    cwd=working_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            (home / ".curlrc").write_text('header = "X-Hostile-Curlrc: loaded"\n', encoding="utf-8")
            env = os.environ.copy()
            env.pop("GH_TOKEN", None)
            env.pop("GITHUB_TOKEN", None)
            env.pop("GITHUB_REPOSITORY", None)
            env.pop("TARIBOY_QUIET_EXIT", None)
            if quiet_code is not None:
                env["TARIBOY_QUIET_EXIT"] = quiet_code
            env.update({
                "HOME": str(home),
                "PWD": str(working_dir),
                "XDG_STATE_HOME": str(xdg_state),
                "XDG_CACHE_HOME": str(xdg_cache),
                "XDG_CONFIG_HOME": str(xdg_config),
                "XDG_DATA_HOME": str(xdg_data),
                "XDG_RUNTIME_DIR": str(xdg_runtime),
                "TMPDIR": str(process_temp),
                "TMP": str(process_temp),
                "TEMP": str(process_temp),
            })
            expected_token = gh_token if gh_token is not None else (github_token if github_token is not None else SECRET)
            env.update(curl.env(expected_token, sandbox))
            if gh_token is not None:
                env["GH_TOKEN"] = gh_token
            if github_token is not None:
                env["GITHUB_TOKEN"] = github_token
            if github_repository is not None:
                env["GITHUB_REPOSITORY"] = github_repository
            result = subprocess.run(
                [sys.executable, str(UTILITY), *args],
                cwd=working_dir,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assert_no_secret_on_disk(sandbox)
            for state_dir in self.absolute_state_dirs(args, sandbox):
                self.assert_no_secret_on_disk(state_dir)
            return result

    def assert_secret_free(self, result):
        self.assertNotIn(SECRET, result.stdout)
        self.assertNotIn(SECRET, result.stderr)

    def assert_no_secret_on_disk(self, root):
        for candidate in root.rglob("*"):
            if candidate.is_file():
                self.assertNotIn(SECRET.encode("utf-8"), candidate.read_bytes(), candidate)

    def absolute_state_dirs(self, args, sandbox):
        state_dirs = []
        for index, arg in enumerate(args[:-1]):
            if arg != "--state-dir":
                continue
            candidate = Path(args[index + 1])
            if candidate.is_absolute() and not candidate.is_relative_to(sandbox):
                state_dirs.append(candidate)
        return state_dirs

    def assert_no_requests(self, curl):
        self.assertEqual(curl.records_json(), [])

    def test_preflight_rejects_missing_token_before_network(self):
        with FakeCurl([]) as curl:
            result = self.run_utility("preflight", "--repo", REPO, curl=curl, gh_token=None)
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_requests(curl)

    def test_preflight_falls_back_to_github_token_without_leaking_it(self):
        with FakeCurl([{"body": {"full_name": REPO}}]) as curl:
            result = self.run_utility("preflight", "--repo", REPO, curl=curl, gh_token=None, github_token=SECRET)
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_secret_free(result)
        self.assertEqual(len(records), 1)
        self.assertNotIn(SECRET, json.dumps(records))

    def test_preflight_gives_gh_token_precedence_and_redacts_invalid_value(self):
        with FakeCurl([{"body": {"full_name": REPO}}]) as curl:
            result = self.run_utility("preflight", "--repo", REPO, curl=curl, gh_token=SECRET, github_token="fallback-token")
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(records), 1)
        with FakeCurl([]) as curl:
            invalid = self.run_utility("preflight", "--repo", REPO, curl=curl, gh_token=SECRET + "\ninvalid", github_token="fallback-token")
        self.assertNotEqual(invalid.returncode, 0)
        self.assert_secret_free(invalid)
        self.assert_no_requests(curl)

    def test_repository_discovery_uses_github_repository_and_configured_origin(self):
        cases = [
            ("environment", {"github_repository": REPO}),
            ("origin", {"origin_url": "git@github.com:alekzonder/tariboy.git"}),
        ]
        for name, discovery in cases:
            with self.subTest(name=name), FakeCurl([{"body": {"full_name": REPO}}]) as curl:
                result = self.run_utility("preflight", curl=curl, **discovery)
                records = curl.records_json()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"ok": True, "repo": REPO})
            self.assertEqual(len(records), 1)
            self.assertIn(f"/repos/{REPO}", records[0]["url"])

    def test_curl_disables_default_config_before_every_other_option(self):
        with FakeCurl([{"body": {"full_name": REPO}}], require_disable=True) as curl:
            result = self.run_utility("preflight", "--repo", REPO, curl=curl)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_secret_free(result)

    def test_curl_output_pipes_are_stopped_at_bounded_sizes(self):
        cases = [
            ("stdout", {"stdout_bytes": 16 * 1024 * 1024}),
            ("stderr", {"stderr_bytes": 1024 * 1024}),
        ]
        for name, response in cases:
            with self.subTest(name=name), FakeCurl([response]) as curl:
                result = self.run_utility("preflight", "--repo", REPO, curl=curl)
                completed = curl.stream_complete.exists()
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(completed, f"curl completed writing oversized {name}")
            self.assertNotIn("Traceback", result.stderr)
            self.assert_secret_free(result)

    def test_ensure_returns_one_existing_open_pull_request(self):
        with FakeCurl([{"body": [pr()]}]) as curl:
            result = self.run_utility("ensure", "--repo", REPO, "--head", HEAD, "--base", BASE, "--title", "TARI-31", curl=curl)
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"created": False, "number": 31, "state": "open", "url": pr()["html_url"]})
        self.assertEqual([record["method"] for record in records], ["GET"])

    def test_ensure_returns_one_existing_closed_pull_request_for_a_decision(self):
        closed = pr(state="closed")
        with FakeCurl([{"body": [closed]}]) as curl:
            result = self.run_utility("ensure", "--repo", REPO, "--head", HEAD, "--base", BASE, "--title", "TARI-31", curl=curl)
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "created": False,
                "number": 31,
                "requires_decision": True,
                "state": "closed",
                "url": closed["html_url"],
            },
        )
        self.assertEqual([record["method"] for record in records], ["GET"])

    def test_ensure_creates_then_reconciles_one_pull_request(self):
        with FakeCurl([{"body": []}, {"body": pr()}, {"body": [pr()]}]) as curl:
            result = self.run_utility("ensure", "--repo", REPO, "--head", HEAD, "--base", BASE, "--title", "TARI-31", curl=curl)
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"created": True, "number": 31, "state": "open", "url": pr()["html_url"]})
        self.assertEqual([record["method"] for record in records], ["GET", "POST", "GET"])
        self.assertEqual(records[1]["json"], {"base": BASE, "head": HEAD, "title": "TARI-31"})

    def test_ensure_reconciles_uncertain_failed_create_to_one_existing_pull_request(self):
        responses = [
            {"body": []},
            {"body": {"message": "upstream response was lost"}, "exit": 22},
            {"body": [pr()]},
        ]
        with FakeCurl(responses) as curl:
            result = self.run_utility(
                "ensure",
                "--repo",
                REPO,
                "--head",
                HEAD,
                "--base",
                BASE,
                "--title",
                "TARI-31",
                curl=curl,
            )
            records = curl.records_json()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"created": False, "number": 31, "state": "open", "url": pr()["html_url"]},
        )
        self.assertEqual([record["method"] for record in records], ["GET", "POST", "GET"])

    def test_ensure_rejects_ambiguous_matches_without_creating(self):
        other = pr(head="def456")
        other["number"] = 32
        with FakeCurl([{"body": [pr(), other]}]) as curl:
            result = self.run_utility("ensure", "--repo", REPO, "--head", HEAD, "--base", BASE, "--title", "TARI-31", curl=curl)
            records = curl.records_json()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("POST", [record["method"] for record in records])


    def test_invalid_repository_and_branch_are_rejected_before_network(self):
        cases = [
            ("preflight", "--repo", "owner/repo;rm"),
            ("ensure", "--repo", REPO, "--head", "bad branch", "--base", BASE, "--title", "TARI-31"),
        ]
        with FakeCurl([]) as curl:
            for args in cases:
                with self.subTest(args=args):
                    result = self.run_utility(*args, curl=curl)
                    self.assertNotEqual(result.returncode, 0)
            self.assert_no_requests(curl)

    def test_monitor_is_not_a_command_of_this_tool(self):
        with FakeCurl([]) as curl:
            result = self.run_utility("monitor", "--repo", REPO, "--pr", "31", "--state-dir", "state", curl=curl)
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid command arguments", result.stderr)
            self.assert_no_requests(curl)


if __name__ == "__main__":
    unittest.main(verbosity=2)
