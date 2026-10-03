#!/usr/bin/env python3
"""Safe, dependency-free GitHub pull-request operations for Tariboy agents:
prove access to a repository and find or create a task's one pull request.
Watching the pull request belongs to the task's workflow, not to this tool."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import subprocess
import sys
import time
from typing import Any, NoReturn
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


API_BASE = "https://api.github.com"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 16 * 1024
COMPONENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
TOKEN_FOR_REDACTION = ""


class WorkflowError(Exception):
    """An actionable, already-safe utility failure."""


class SafeArgumentParser(argparse.ArgumentParser):
    """Keep invalid user input out of diagnostics."""

    def error(self, message: str) -> NoReturn:
        raise WorkflowError("invalid command arguments")


def fail(message: str) -> NoReturn:
    raise WorkflowError(message)


def redact_text(value: str) -> str:
    if TOKEN_FOR_REDACTION:
        return value.replace(TOKEN_FOR_REDACTION, "[REDACTED]")
    return value


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    return value


def emit_json(value: Any) -> None:
    encoded = json.dumps(
        redact_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    sys.stdout.write(encoded + "\n")


def validate_component(value: str, label: str) -> str:
    if not value or not COMPONENT_RE.fullmatch(value) or value in {".", ".."}:
        fail(f"invalid {label}")
    return value


def validate_repo(value: str) -> tuple[str, str]:
    if value.count("/") != 1:
        fail("repository must use OWNER/REPO")
    owner, name = value.split("/", 1)
    return validate_component(owner, "repository owner"), validate_component(
        name, "repository name"
    )


def repo_from_origin() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError("cannot resolve the configured origin remote") from exc
    if result.returncode != 0 or len(result.stdout) > 4096:
        fail("repository is required and origin is unavailable")
    remote = result.stdout.strip()
    if CONTROL_RE.search(remote):
        fail("origin remote contains invalid characters")

    candidate = ""
    if remote.startswith("git@github.com:"):
        candidate = remote[len("git@github.com:") :]
    else:
        parsed = urlparse(remote)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            fail("origin remote is not a supported GitHub URL")
        candidate = parsed.path.lstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    validate_repo(candidate)
    return candidate


def resolve_repo(explicit: str | None) -> tuple[str, str]:
    value = explicit or os.environ.get("GITHUB_REPOSITORY") or repo_from_origin()
    return validate_repo(value)


def validate_branch(value: str, label: str) -> str:
    if not value or CONTROL_RE.search(value) or len(value.encode("utf-8")) > 1024:
        fail(f"invalid {label} branch")
    try:
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", value],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError("git is required to validate branch names") from exc
    if result.returncode != 0:
        fail(f"invalid {label} branch")
    return value


def select_token() -> str:
    global TOKEN_FOR_REDACTION
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        fail("GH_TOKEN or GITHUB_TOKEN is required")
    TOKEN_FOR_REDACTION = token
    if CONTROL_RE.search(token) or len(token.encode("utf-8")) > 8192:
        fail("GitHub token contains invalid characters")
    return token


def resolve_curl() -> str:
    override = os.environ.get("TARIBOY_GITHUB_CURL_BIN")
    if override:
        if CONTROL_RE.search(override) or not os.path.isabs(override):
            fail("TARIBOY_GITHUB_CURL_BIN must be an absolute executable path")
        path = Path(override)
        try:
            info = path.lstat()
        except OSError as exc:
            raise WorkflowError("configured curl executable is unavailable") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            fail("configured curl executable must be a non-symlink regular file")
        if not os.access(path, os.X_OK):
            fail("configured curl executable is not executable")
        if TOKEN_FOR_REDACTION and TOKEN_FOR_REDACTION in str(path):
            fail("configured curl path contains credential material")
        return str(path)
    curl = shutil.which("curl")
    if not curl:
        fail("curl is required")
    return curl


def append_query(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.extend((key, str(value)) for key, value in params.items())
    return urlunparse(parsed._replace(query=urlencode(query)))


def extend_bounded_collection(
    items: list[Any], values: list[Any], encoded_size: int
) -> int:
    for value in values:
        item_size = len(
            json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
        encoded_size += item_size + (1 if items else 0)
        if encoded_size > MAX_RESPONSE_BYTES:
            fail("GitHub paginated collection exceeded its size limit")
        items.append(value)
    return encoded_size


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError("failed to reap curl after termination") from exc


def bounded_process_output(process: subprocess.Popen[bytes]) -> tuple[bytes, bytes]:
    if process.stdout is None or process.stderr is None:
        fail("curl output pipes are unavailable")
    streams = {
        process.stdout.fileno(): ("response", process.stdout, MAX_RESPONSE_BYTES),
        process.stderr.fileno(): ("diagnostic", process.stderr, MAX_DIAGNOSTIC_BYTES),
    }
    buffers = {"response": bytearray(), "diagnostic": bytearray()}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + 35
    try:
        for descriptor in streams:
            os.set_blocking(descriptor, False)
            selector.register(descriptor, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process(process)
                fail("GitHub request exceeded its time limit")
            events = selector.select(remaining)
            if not events:
                stop_process(process)
                fail("GitHub request exceeded its time limit")
            for key, _ in events:
                descriptor = key.fd
                try:
                    chunk = os.read(descriptor, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(descriptor)
                    continue
                label, _, limit = streams[descriptor]
                buffers[label].extend(chunk)
                if len(buffers[label]) > limit:
                    stop_process(process)
                    fail(f"GitHub {label} exceeded its size limit")
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            stop_process(process)
            fail("GitHub request exceeded its time limit")
        return bytes(buffers["response"]), bytes(buffers["diagnostic"])
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


class GitHubClient:
    def __init__(self, token: str, curl_bin: str):
        self.token = token
        self.curl_bin = curl_bin

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        if not path.startswith("/") or "//" in path or CONTROL_RE.search(path):
            fail("invalid GitHub API path")
        url = API_BASE + path
        if params:
            url = append_query(url, params)
        if self.token in url:
            fail("refusing to place the GitHub token in a URL")

        args = [
            self.curl_bin,
            "--disable",
            "--silent",
            "--show-error",
            "--fail-with-body",
            "--connect-timeout",
            "10",
            "--max-time",
            "30",
            "--max-filesize",
            str(MAX_RESPONSE_BYTES),
            "--config",
            "CONFIG_FD",
            "--header",
            "Accept: application/vnd.github+json",
            "--header",
            "X-GitHub-Api-Version: 2022-11-28",
        ]
        if method != "GET":
            args.extend(["--request", method])
        if body is not None:
            encoded_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            if self.token in encoded_body:
                fail("refusing to place the GitHub token in request arguments")
            args.extend(["--data-binary", encoded_body])
        args.append(url)

        read_fd, write_fd = os.pipe()
        args[args.index("CONFIG_FD")] = f"/dev/fd/{read_fd}"
        escaped = self.token.replace("\\", "\\\\").replace('"', '\\"')
        config = f'header = "Authorization: Bearer {escaped}"\n'.encode("utf-8")
        env = os.environ.copy()
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                pass_fds=(read_fd,),
            )
            os.close(read_fd)
            read_fd = -1
            view = memoryview(config)
            while view:
                written = os.write(write_fd, view)
                view = view[written:]
            os.close(write_fd)
            write_fd = -1
            stdout, stderr = bounded_process_output(process)
        except OSError as exc:
            if process is not None:
                stop_process(process)
            raise WorkflowError("failed to execute curl") from exc
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)

        if process.returncode != 0:
            fail(f"GitHub request failed (curl exit {process.returncode})")
        try:
            return json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError("GitHub returned malformed JSON") from exc

    def paginated_array(self, path: str, *, params: dict[str, Any] | None = None) -> list[Any]:
        items: list[Any] = []
        encoded_size = 2
        page = 1
        while True:
            page_params = dict(params or {})
            page_params.update({"per_page": 100, "page": page})
            response = self.request("GET", path, params=page_params)
            if not isinstance(response, list):
                fail("GitHub returned an unexpected array response")
            encoded_size = extend_bounded_collection(items, response, encoded_size)
            if len(response) < 100:
                return items
            page += 1

    def paginated_check_runs(self, path: str) -> list[Any]:
        items: list[Any] = []
        encoded_size = 2
        page = 1
        while True:
            response = self.request(
                "GET", path, params={"per_page": 100, "page": page}
            )
            if not isinstance(response, dict):
                fail("GitHub returned an unexpected check-runs response")
            total = response.get("total_count")
            current = response.get("check_runs")
            if not isinstance(total, int) or total < 0 or not isinstance(current, list):
                fail("GitHub returned an incomplete check-runs response")
            encoded_size = extend_bounded_collection(items, current, encoded_size)
            if len(current) < 100:
                return items
            page += 1


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"GitHub returned an unexpected {label} response")
    return value


def integer_field(value: dict[str, Any], key: str, label: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        fail(f"GitHub {label} has an invalid {key}")
    return item


def text_field(
    value: dict[str, Any], key: str, label: str, *, nullable: bool = False
) -> str | None:
    item = value.get(key)
    if nullable and item is None:
        return None
    if not isinstance(item, str) or CONTROL_RE.search(item) or len(item) > MAX_RESPONSE_BYTES:
        fail(f"GitHub {label} has an invalid {key}")
    return redact_text(item)


def validate_pr_result(value: Any) -> dict[str, Any]:
    item = require_dict(value, "pull request")
    number = integer_field(item, "number", "pull request")
    if number <= 0:
        fail("GitHub pull request has an invalid number")
    state = text_field(item, "state", "pull request")
    if state not in {"open", "closed"}:
        fail("GitHub pull request has an invalid state")
    url = text_field(item, "html_url", "pull request")
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        fail("GitHub pull request has an invalid URL")
    return {"number": number, "state": state, "url": url}


def canonical_pull(items: list[Any]) -> dict[str, Any] | None:
    pulls = [validate_pr_result(item) for item in items]
    if len(pulls) > 1:
        fail("multiple pull requests match the requested head and base")
    return pulls[0] if pulls else None


def pull_query(client: GitHubClient, owner: str, repo: str, head: str, base: str) -> list[Any]:
    return client.paginated_array(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "all", "head": f"{owner}:{head}", "base": base},
    )


def command_preflight(args: argparse.Namespace, client: GitHubClient) -> int:
    owner, repo = args.resolved_repo
    response = require_dict(client.request("GET", f"/repos/{owner}/{repo}"), "repository")
    full_name = text_field(response, "full_name", "repository")
    if (full_name or "").casefold() != f"{owner}/{repo}".casefold():
        fail("authenticated repository response does not match the requested repository")
    emit_json({"ok": True, "repo": full_name})
    return 0


def command_ensure(args: argparse.Namespace, client: GitHubClient) -> int:
    owner, repo = args.resolved_repo
    existing = canonical_pull(pull_query(client, owner, repo, args.head, args.base))
    if existing is not None:
        result = {"created": False, **existing}
        if existing["state"] == "closed":
            result["requires_decision"] = True
        emit_json(result)
        return 0

    create_body: dict[str, Any] = {
        "base": args.base,
        "head": args.head,
        "title": args.title,
    }
    if args.body is not None:
        create_body["body"] = args.body
    create_error: WorkflowError | None = None
    created = False
    try:
        validate_pr_result(
            client.request("POST", f"/repos/{owner}/{repo}/pulls", body=create_body)
        )
        created = True
    except WorkflowError as exc:
        create_error = exc

    try:
        reconciled = canonical_pull(pull_query(client, owner, repo, args.head, args.base))
    except WorkflowError:
        if create_error is not None:
            raise create_error
        raise
    if reconciled is None:
        if create_error is not None:
            raise create_error
        fail("pull request creation did not reconcile to one open pull request")
    result = {"created": created, **reconciled}
    if reconciled["state"] == "closed":
        result["requires_decision"] = True
    emit_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="Safe GitHub pull-request operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--repo")

    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--repo")
    ensure.add_argument("--head", required=True)
    ensure.add_argument("--base", required=True)
    ensure.add_argument("--title", required=True)
    ensure.add_argument("--body")
    return parser


def main() -> int:
    global TOKEN_FOR_REDACTION
    TOKEN_FOR_REDACTION = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    args = build_parser().parse_args()
    args.resolved_repo = resolve_repo(args.repo)
    if args.command == "ensure":
        args.head = validate_branch(args.head, "head")
        args.base = validate_branch(args.base, "base")
        if not args.title or "\x00" in args.title:
            fail("pull request title must be non-empty")
        if args.body is not None and "\x00" in args.body:
            fail("pull request body contains invalid characters")

    token = select_token()
    client = GitHubClient(token, resolve_curl())
    if args.command == "preflight":
        if sys.version_info < (3, 9) or shutil.which("python3") is None:
            fail("Python 3 is required")
        return command_preflight(args, client)
    return command_ensure(args, client)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkflowError as exc:
        diagnostic = redact_text(str(exc)).replace("\n", " ").replace("\r", " ")
        sys.stderr.write(f"github-pr: {diagnostic[:MAX_DIAGNOSTIC_BYTES]}\n")
        raise SystemExit(1)
