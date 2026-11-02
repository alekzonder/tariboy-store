#!/usr/bin/env python3
"""A stand-in for curl that answers GitHub REST API requests from local state.

The workflow eval runner copies this file next to a `github.json` state file
and points TARIBOY_GITHUB_CURL_BIN at the copy. The development workflow's
scripts and the developer image's github-pr-workflow utility then talk to this
fake instead of api.github.com. Pull request heads are read from the bare
repository that stands in for the GitHub remote, so a `git push` by the agent
is visible here.

State file (github.json):

    {
      "repos": {
        "OWNER/REPO": {
          "bare": "/abs/path/origin.git",
          "default_branch": "main",
          "pulls": [
            {"number": 1, "head": "feature", "base": "main", "title": "...",
             "body": "...", "state": "open", "merged": false,
             "merge_commit_sha": null, "head_sha": null}
          ]
        }
      }
    }

A pull with `head_sha` null reports the current tip of its head branch in the
bare repository. Every request is appended to `requests.log` next to the
state file. Only the request forms the clients use are parsed.

The runner also serves `handle` over loopback HTTP for the workflow's own
scripts, which reach it through their GITHUB_API_URL test seam: a queue env
var may not start with TARIBOY_, so TARIBOY_GITHUB_CURL_BIN cannot reach them.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
STATE = HERE / "github.json"
LOG = HERE / "requests.log"
LOCK = HERE / "github.lock"
API_HOST = "api.github.com"
VALUE_OPTIONS = {
    "--connect-timeout",
    "--max-time",
    "--max-filesize",
    "--config",
    "--header",
    "-H",
    "--write-out",
    "-w",
    "--dump-header",
    "-D",
    "--request",
    "-X",
    "--data-binary",
    "--data",
    "-d",
    "--output",
    "-o",
}


class Answer(Exception):
    def __init__(self, status: int, body: object):
        super().__init__(status)
        self.status = status
        self.body = body


def parse_args(argv: list[str]) -> dict:
    options: dict = {"method": None, "data": None, "write_out": None, "url": None, "fail": False}
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in VALUE_OPTIONS:
            value = argv[index + 1] if index + 1 < len(argv) else ""
            if arg in {"--request", "-X"}:
                options["method"] = value
            elif arg in {"--data-binary", "--data", "-d"}:
                options["data"] = value
            elif arg in {"--write-out", "-w"}:
                options["write_out"] = value
            elif arg in {"--dump-header", "-D"}:
                options["dump_header"] = value
            index += 2
            continue
        if arg in {"--fail-with-body", "--fail", "-f"}:
            options["fail"] = True
        elif not arg.startswith("-"):
            options["url"] = arg
        index += 1
    if options["method"] is None:
        options["method"] = "POST" if options["data"] is not None else "GET"
    return options


def git(bare: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", bare, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def branch_sha(repo: dict, branch: str) -> str:
    return git(repo["bare"], "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}")


def pull_view(full_name: str, repo: dict, pull: dict) -> dict:
    head_sha = pull.get("head_sha") or branch_sha(repo, pull["head"])
    base_sha = branch_sha(repo, pull["base"])
    state = pull.get("state", "open")
    merged = bool(pull.get("merged"))
    number = pull["number"]
    return {
        "number": number,
        "html_url": f"https://github.com/{full_name}/pull/{number}",
        "url": f"https://api.github.com/repos/{full_name}/pulls/{number}",
        "state": state,
        "merged": merged,
        "merged_at": "2026-01-01T00:00:00Z" if merged else None,
        "closed_at": "2026-01-01T00:00:00Z" if state == "closed" else None,
        "merge_commit_sha": pull.get("merge_commit_sha"),
        "mergeable": None if merged else pull.get("mergeable", True),
        "mergeable_state": "clean",
        "draft": False,
        "title": pull.get("title", ""),
        "body": pull.get("body"),
        "user": {"login": pull.get("author", "eval-developer")},
        "head": {
            "ref": pull["head"],
            "sha": head_sha,
            "repo": {"full_name": full_name},
            "label": f"{full_name.split('/')[0]}:{pull['head']}",
        },
        "base": {"ref": pull["base"], "sha": base_sha, "repo": {"full_name": full_name}},
    }


def find_pull(repo: dict, number: str) -> dict:
    for pull in repo["pulls"]:
        if str(pull["number"]) == number:
            return pull
    raise Answer(404, {"message": "Not Found"})


def route(state: dict, method: str, path: str, query: dict, data: str | None) -> tuple[int, object]:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "repos":
        raise Answer(404, {"message": "Not Found"})
    full_name = f"{parts[1]}/{parts[2]}"
    repo = state["repos"].get(full_name)
    if repo is None:
        raise Answer(404, {"message": "Not Found"})
    repo.setdefault("pulls", [])
    rest = parts[3:]
    page = int((query.get("page") or ["1"])[0])

    if not rest and method == "GET":
        return 200, {
            "full_name": full_name,
            "default_branch": repo.get("default_branch", "main"),
            "allow_merge_commit": True,
            "allow_rebase_merge": True,
            "allow_squash_merge": True,
            "permissions": {"admin": False, "push": True, "pull": True},
        }
    if rest == ["pulls"] and method == "GET":
        if page > 1:
            return 200, []
        head = (query.get("head") or [None])[0]
        base = (query.get("base") or [None])[0]
        wanted = (query.get("state") or ["open"])[0]
        found = []
        for pull in repo["pulls"]:
            if head is not None and f"{parts[1]}:{pull['head']}" != head:
                continue
            if base is not None and pull["base"] != base:
                continue
            if wanted != "all" and pull.get("state", "open") != wanted:
                continue
            found.append(pull_view(full_name, repo, pull))
        return 200, found
    if rest == ["pulls"] and method == "POST":
        body = json.loads(data or "{}")
        head, base = body.get("head"), body.get("base")
        if not head or not base or not branch_sha(repo, head) or not branch_sha(repo, base):
            raise Answer(422, {"message": "Validation Failed"})
        for pull in repo["pulls"]:
            if pull["head"] == head and pull["base"] == base and pull.get("state", "open") == "open":
                raise Answer(422, {"message": "A pull request already exists"})
        pull = {
            "number": max([p["number"] for p in repo["pulls"]] + [0]) + 1,
            "head": head,
            "base": base,
            "title": body.get("title", ""),
            "body": body.get("body"),
            "state": "open",
            "merged": False,
        }
        repo["pulls"].append(pull)
        return 201, pull_view(full_name, repo, pull)
    if len(rest) == 2 and rest[0] == "pulls":
        pull = find_pull(repo, rest[1])
        if method == "GET":
            return 200, pull_view(full_name, repo, pull)
        if method == "PATCH":
            body = json.loads(data or "{}")
            for field in ("title", "body", "state"):
                if field in body:
                    pull[field] = body[field]
            return 200, pull_view(full_name, repo, pull)
    if len(rest) == 3 and rest[0] == "pulls" and rest[2] in {"comments", "reviews"}:
        find_pull(repo, rest[1])
        if method == "GET":
            return 200, [] if page > 1 else list(repo.get(f"pull_{rest[2]}", {}).get(rest[1], []))
    if len(rest) == 3 and rest[0] == "issues" and rest[2] == "comments":
        comments = repo.setdefault("issue_comments", {}).setdefault(rest[1], [])
        if method == "GET":
            return 200, [] if page > 1 else list(comments)
        if method == "POST":
            body = json.loads(data or "{}")
            comment = {
                "id": 1000 + len(comments),
                "body": body.get("body", ""),
                "user": {"login": "eval-developer"},
                "html_url": f"https://github.com/{full_name}/pull/{rest[1]}#issuecomment-{1000 + len(comments)}",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
            comments.append(comment)
            return 201, comment
    if len(rest) == 3 and rest[0] == "commits" and method == "GET":
        if rest[2] == "check-runs":
            return 200, {"total_count": 0, "check_runs": []}
        if rest[2] == "statuses":
            return 200, []
        if rest[2] == "status":
            return 200, {"state": "pending", "statuses": [], "total_count": 0}
    raise Answer(404, {"message": "Not Found"})


def handle(directory: Path, method: str, path: str, query: str, data: str | None) -> tuple[int, object]:
    """Answer one API request from the state in `directory` and log it."""
    with (directory / LOCK.name).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = directory / STATE.name
        state = json.loads(state_path.read_text())
        try:
            status, body = route(state, method, path, parse_qs(query), data)
            state_path.write_text(json.dumps(state, indent=2) + "\n")
        except Answer as answer:
            status, body = answer.status, answer.body
        with (directory / LOG.name).open("a") as log:
            log.write(f"{method} {path}{'?' + query if query else ''} -> {status}\n")
    return status, body


def main() -> int:
    argv = sys.argv[1:]
    if argv == ["--version"]:
        sys.stdout.write("curl 8.5.0 (fake-github) libcurl/8.5.0\n")
        return 0
    options = parse_args(argv)
    url = urlparse(options["url"] or "")
    if url.hostname != API_HOST:
        status, body = 404, {"message": "Not Found"}
    else:
        status, body = handle(HERE, options["method"], url.path, url.query, options["data"])
    sys.stdout.write(json.dumps(body))
    if options["write_out"] is not None:
        out = options["write_out"].replace("%{http_code}", str(status))
        while "%header{" in out:
            start = out.index("%header{")
            end = out.index("}", start)
            out = out[:start] + out[end + 1 :]
        sys.stdout.write(out.replace("\\n", "\n"))
    if options.get("dump_header"):
        Path(options["dump_header"]).write_text(f"HTTP/2 {status}\r\n\r\n")
    if status >= 400 and options["fail"]:
        return 22
    return 0


if __name__ == "__main__":
    sys.exit(main())
