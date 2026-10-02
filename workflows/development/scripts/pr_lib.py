#!/usr/bin/env python3
"""Shared protocol and GitHub helpers for the development workflow scripts.

The GitHub client is the bounded, redacting curl client of the
github-pr-workflow utility; only the API root differs: it comes from
GITHUB_API_URL. The token stays in the process environment and reaches curl
through an inherited config descriptor, never an argument, a URL, or a file.
"""

from __future__ import annotations

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
from typing import Any, Callable, NoReturn
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _exit_code(name: str, default: int) -> int:
    value = os.environ.get(name, "")
    return int(value) if value.isascii() and value.isdigit() else default


QUIET_EXIT: int = _exit_code("TARIBOY_QUIET_EXIT", 111)
REJECT_EXIT: int = _exit_code("TARIBOY_REJECT_EXIT", 112)

DEFAULT_API_BASE = "https://api.github.com"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 16 * 1024
MAX_MESSAGE_CHARS = 4000
MAX_MESSAGE_BYTES = 4096
DEFAULT_PAGINATE_LIMIT = 10000
COMPONENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
PULL_REQUEST_PREFIX = "https://github.com/"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
TOKEN_FOR_REDACTION = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


class ScriptFailure(Exception):
    """An already-safe failure: exit 1 with a bounded diagnostic on stderr."""


class GitHubHTTPError(ScriptFailure):
    """GitHub answered with an HTTP status outside 2xx."""

    def __init__(self, status: int):
        super().__init__(f"GitHub answered HTTP {status}")
        self.status = status


def fail(message: str) -> NoReturn:
    raise ScriptFailure(message)


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


def run(main: Callable[[], int]) -> NoReturn:
    """Run a script's main and turn a ScriptFailure into exit 1."""
    try:
        code = main()
    except ScriptFailure as exc:
        diagnostic = redact_text(str(exc)).replace("\n", " ").replace("\r", " ")
        name = Path(sys.argv[0]).name or "script"
        sys.stderr.write(f"{name}: {diagnostic[:MAX_DIAGNOSTIC_BYTES]}\n")
        raise SystemExit(1)
    raise SystemExit(code)


def load_task() -> dict:
    path = os.environ.get("TARIBOY_TASK_FILE")
    if not path:
        fail("TARIBOY_TASK_FILE is not set")
    try:
        with open(path, "rb") as source:
            data = source.read(MAX_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise ScriptFailure("the task snapshot is unreadable") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        fail("the task snapshot exceeds its size limit")
    try:
        task = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScriptFailure("the task snapshot is malformed") from exc
    if not isinstance(task, dict):
        fail("the task snapshot has an unexpected shape")
    return task


def artifact(task: dict, name: str) -> str | None:
    items = task.get("artifacts")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            value = item.get("value")
            return value if isinstance(value, str) else None
    return None


def validate_component(value: str, label: str) -> str:
    if not value or not COMPONENT_RE.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"invalid {label}")
    return value


def validate_pr_number(value: str) -> int:
    if not value.isascii() or not value.isdigit():
        raise ValueError("pull request number must be a positive integer")
    number = int(value)
    if number <= 0:
        raise ValueError("pull request number must be a positive integer")
    return number


def validate_branch(value: str, label: str) -> str:
    """A local branch name that git accepts and no option parser can mistake."""
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("-")
        or "@{" in value
        or CONTROL_RE.search(value)
        or len(value.encode("utf-8")) > 1024
    ):
        raise ValueError(f"invalid {label} branch")
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
        raise ScriptFailure("git is required to validate branch names") from exc
    if result.returncode != 0:
        raise ValueError(f"invalid {label} branch")
    return value


def parse_pull_request_url(value: str) -> tuple[str, str, int]:
    """Accept only https://github.com/OWNER/REPO/pull/N, with nothing after N."""
    if not isinstance(value, str) or not value.startswith(PULL_REQUEST_PREFIX):
        raise ValueError("not a GitHub pull request URL")
    parts = value[len(PULL_REQUEST_PREFIX) :].split("/")
    if len(parts) != 4 or parts[2] != "pull":
        raise ValueError("not a GitHub pull request URL")
    owner = validate_component(parts[0], "repository owner")
    repo = validate_component(parts[1], "repository name")
    number_text = parts[3]
    if number_text.startswith("0"):
        raise ValueError("pull request number must be a positive integer")
    return owner, repo, validate_pr_number(number_text)


def _bounded_message(message: str) -> str:
    message = message[:MAX_MESSAGE_CHARS]
    while len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        message = message[:-1]
    return message


def write_result(
    *,
    outcome: str | None = None,
    message: str = "",
    artifacts: dict[str, str] | None = None,
) -> None:
    path = os.environ.get("TARIBOY_RESULT_FILE")
    if not path:
        fail("TARIBOY_RESULT_FILE is not set")
    result: dict[str, Any] = {}
    if outcome is not None:
        result["outcome"] = outcome
    result["message"] = _bounded_message(redact_text(message))
    if artifacts is not None:
        result["artifacts"] = redact_value(dict(artifacts))
    payload = json.dumps(result, ensure_ascii=False) + "\n"
    try:
        with open(path, "w", encoding="utf-8") as output:
            output.write(payload)
    except OSError as exc:
        raise ScriptFailure("cannot write the result file") from exc


def select_token() -> str:
    global TOKEN_FOR_REDACTION
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        fail("GH_TOKEN or GITHUB_TOKEN is required")
    TOKEN_FOR_REDACTION = token
    if CONTROL_RE.search(token) or len(token.encode("utf-8")) > 8192:
        fail("GitHub token contains invalid characters")
    return token


def resolve_api_base() -> str:
    value = os.environ.get("GITHUB_API_URL") or DEFAULT_API_BASE
    if CONTROL_RE.search(value):
        fail("GITHUB_API_URL is invalid")
    if TOKEN_FOR_REDACTION and TOKEN_FOR_REDACTION in value:
        fail("GITHUB_API_URL contains credential material")
    parsed = urlparse(value)
    try:
        parsed.port
    except ValueError as exc:
        raise ScriptFailure("GITHUB_API_URL is invalid") from exc
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        fail("GITHUB_API_URL is invalid")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS
    ):
        fail("GITHUB_API_URL must use https (http only for a loopback host)")
    return value.rstrip("/")


def resolve_curl() -> str:
    override = os.environ.get("TARIBOY_GITHUB_CURL_BIN")
    if override:
        if CONTROL_RE.search(override) or not os.path.isabs(override):
            fail("TARIBOY_GITHUB_CURL_BIN must be an absolute executable path")
        path = Path(override)
        try:
            info = path.lstat()
        except OSError as exc:
            raise ScriptFailure("configured curl executable is unavailable") from exc
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


def extend_bounded_collection(items: list[Any], values: list[Any], encoded_size: int) -> int:
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
        raise ScriptFailure("failed to reap curl after termination") from exc


def bounded_process_output(
    process: subprocess.Popen[bytes], limit_seconds: float = 35
) -> tuple[bytes, bytes]:
    if process.stdout is None or process.stderr is None:
        fail("curl output pipes are unavailable")
    streams = {
        process.stdout.fileno(): ("response", process.stdout, MAX_RESPONSE_BYTES),
        process.stderr.fileno(): ("diagnostic", process.stderr, MAX_DIAGNOSTIC_BYTES),
    }
    buffers = {"response": bytearray(), "diagnostic": bytearray()}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + limit_seconds
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


# curl appends this after the body so the status survives --fail-with-body.
STATUS_MARKER = b"\n#tariboy-http-status:"


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        curl_bin: str | None = None,
        deadline: float | None = None,
    ):
        """`deadline`, a time.monotonic() value, bounds every request of the
        client together: no request starts after it or runs past it."""
        self.token = token if token is not None else select_token()
        self.api_base = resolve_api_base()
        self.curl_bin = curl_bin if curl_bin is not None else resolve_curl()
        self.deadline = deadline

    def _time_limits(self) -> tuple[int, int, float]:
        """Connect timeout, curl --max-time, and the output deadline."""
        if self.deadline is None:
            return 10, 30, 35
        remaining = self.deadline - time.monotonic()
        if remaining < 1:
            fail("the run exceeded its overall time limit")
        seconds = min(30, int(remaining))
        return min(10, seconds), seconds, min(35.0, remaining)

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
        url = self.api_base + path
        if params:
            url = append_query(url, params)
        if self.token in url:
            fail("refusing to place the GitHub token in a URL")
        connect_timeout, max_time, output_limit = self._time_limits()

        args = [
            self.curl_bin,
            "--disable",
            "--silent",
            "--show-error",
            "--fail-with-body",
            "--connect-timeout",
            str(connect_timeout),
            "--max-time",
            str(max_time),
            "--max-filesize",
            str(MAX_RESPONSE_BYTES),
            "--config",
            "CONFIG_FD",
            "--header",
            "Accept: application/vnd.github+json",
            "--header",
            "X-GitHub-Api-Version: 2022-11-28",
            "--write-out",
            STATUS_MARKER.decode("ascii") + "%{http_code}",
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
            stdout, _ = bounded_process_output(process, output_limit)
        except OSError as exc:
            if process is not None:
                stop_process(process)
            raise ScriptFailure("failed to execute curl") from exc
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)

        response, marker, status_text = stdout.rpartition(STATUS_MARKER)
        status = int(status_text) if marker and status_text.isdigit() else 0
        if status >= 300 or (process.returncode == 22 and status):
            raise GitHubHTTPError(status)
        if process.returncode != 0:
            fail(f"GitHub request failed (curl exit {process.returncode})")
        if not marker or not 200 <= status < 300:
            fail("GitHub returned an incomplete response")
        try:
            return json.loads(response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScriptFailure("GitHub returned malformed JSON") from exc

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.request("GET", path, params=params)

    def paginate(
        self, path: str, params: dict | None = None, limit: int = DEFAULT_PAGINATE_LIMIT
    ) -> list:
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
            if len(items) > limit:
                fail("GitHub paginated collection exceeded its item limit")
            if len(response) < 100:
                return items
            page += 1

    def paginated_check_runs(self, path: str, limit: int = DEFAULT_PAGINATE_LIMIT) -> list:
        items: list[Any] = []
        encoded_size = 2
        page = 1
        while True:
            response = self.request("GET", path, params={"per_page": 100, "page": page})
            if not isinstance(response, dict):
                fail("GitHub returned an unexpected check-runs response")
            total = response.get("total_count")
            current = response.get("check_runs")
            if not isinstance(total, int) or total < 0 or not isinstance(current, list):
                fail("GitHub returned an incomplete check-runs response")
            encoded_size = extend_bounded_collection(items, current, encoded_size)
            if len(items) > limit:
                fail("GitHub paginated collection exceeded its item limit")
            if len(current) < 100:
                return items
            page += 1
