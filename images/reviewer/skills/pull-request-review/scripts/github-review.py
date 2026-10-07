#!/usr/bin/env python3
"""Fetch, check and publish a GitHub pull request review.

  github-review.py fetch   --pr URL --out DIR   (pull.json, files.json, diff.patch, anchors.diff)
  github-review.py check   --pr URL --head-sha SHA --comments FILE
  github-review.py publish --pr URL --head-sha SHA --comments FILE

URL is https://github.com/OWNER/REPO/pull/NUMBER. FILE holds review_comments
JSON ({"body": ..., "comments": [...]}); "-" reads it from standard input.
Every command prints one JSON object on stdout. Exit 0 on success, 2 when the
input is invalid or GitHub would refuse the review (the "error" says why), 1
on any other failure. The token comes from GH_TOKEN or GITHUB_TOKEN and
reaches curl only through an inherited descriptor.

publish creates one review with the event COMMENT on the given commit. Its
body ends with a hidden marker derived from the commit and the comments, so a
repeated publish of the same review prints the existing review's URL instead
of creating a second one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_client as gh  # noqa: E402
import review_lib  # noqa: E402

SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
INVALID_EXIT = 2


class Invalid(Exception):
    """Input the caller must fix: exit 2."""


def emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parse_pr(value: str) -> tuple[str, str, int]:
    try:
        return gh.parse_pull_request_url(value)
    except ValueError as exc:
        raise Invalid(f"--pr must be https://github.com/OWNER/REPO/pull/NUMBER: {exc}") from exc


def parse_sha(value: str) -> str:
    if not SHA_RE.fullmatch(value or ""):
        raise Invalid("--head-sha must be a full lowercase commit SHA")
    return value


def read_comments(path: str) -> dict:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Invalid(f"cannot read {path}") from exc
    try:
        return review_lib.parse_review_comments(text)
    except review_lib.InvalidReview as exc:
        raise Invalid(str(exc)) from exc


def pull_head(client: gh.GitHubClient, owner: str, repo: str, number: int) -> dict:
    pull = client.get(f"/repos/{owner}/{repo}/pulls/{number}")
    if not isinstance(pull, dict) or not isinstance(pull.get("head"), dict):
        gh.fail("GitHub returned an unexpected pull request")
    return pull


def files_of(client: gh.GitHubClient, owner: str, repo: str, number: int) -> list:
    return client.paginate(f"/repos/{owner}/{repo}/pulls/{number}/files", limit=3000)


def command_fetch(args: argparse.Namespace) -> int:
    owner, repo, number = parse_pr(args.pr)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = gh.GitHubClient()
    pull = pull_head(client, owner, repo, number)
    files = files_of(client, owner, repo, number)
    keep = ("number", "state", "draft", "merged", "title", "body", "html_url")
    summary = {key: pull.get(key) for key in keep}
    summary["author"] = (pull.get("user") or {}).get("login")
    summary["head"] = {k: pull["head"].get(k) for k in ("sha", "ref")}
    summary["base"] = {k: (pull.get("base") or {}).get(k) for k in ("sha", "ref")}
    summary["clone_url"] = ((pull.get("base") or {}).get("repo") or {}).get("clone_url")
    (out / "pull.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "files.json").write_text(json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8")
    without_diff = []
    with open(out / "diff.patch", "w", encoding="utf-8") as diff, open(
        out / "anchors.diff", "w", encoding="utf-8"
    ) as anchors:
        for item in files:
            name = item.get("filename")
            diff.write(f"diff --git a/{item.get('previous_filename') or name} b/{name}\n")
            anchors.write(f"=== {name}\n")
            if isinstance(item.get("patch"), str):
                diff.write(item["patch"].rstrip("\n") + "\n")
                anchors.write("\n".join(review_lib.annotate(item["patch"])) + "\n")
            else:
                without_diff.append(name)
                anchors.write("(no diff: anchor nothing here)\n")
    emit(
        {
            "pull_request": f"https://github.com/{owner}/{repo}/pull/{number}",
            "head_sha": summary["head"]["sha"],
            "state": summary["state"],
            "files": len(files),
            "files_without_diff": without_diff,
            "out": str(out),
            "untrusted": ["pull.json title and body", "diff.patch content"],
        }
    )
    return 0


def check_review(client: gh.GitHubClient, owner: str, repo: str, number: int, sha: str, review: dict) -> str:
    pull = pull_head(client, owner, repo, number)
    current = pull["head"].get("sha")
    if review["comments"]:
        problems = review_lib.anchor_problems(review["comments"], files_of(client, owner, repo, number))
        if problems:
            raise Invalid("GitHub would refuse these inline comments: " + "; ".join(problems))
    return current


def command_check(args: argparse.Namespace) -> int:
    owner, repo, number = parse_pr(args.pr)
    sha = parse_sha(args.head_sha)
    review = read_comments(args.comments)
    current = check_review(gh.GitHubClient(), owner, repo, number, sha, review)
    if current != sha:
        raise Invalid(f"the pull request's head is now {current}, not {sha}: review the new head")
    emit({"ok": True, "head_sha": sha, "comments": len(review["comments"])})
    return 0


def marker_for(sha: str, review: dict) -> str:
    canonical = json.dumps([sha, review], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"<!-- pull-request-review:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]} -->"


def command_publish(args: argparse.Namespace) -> int:
    owner, repo, number = parse_pr(args.pr)
    sha = parse_sha(args.head_sha)
    review = read_comments(args.comments)
    client = gh.GitHubClient()
    marker = marker_for(sha, review)
    base = f"https://github.com/{owner}/{repo}/pull/{number}"
    for existing in client.paginate(f"/repos/{owner}/{repo}/pulls/{number}/reviews", limit=3000):
        if isinstance(existing, dict) and marker in (existing.get("body") or ""):
            emit({"url": f"{base}#pullrequestreview-{existing.get('id')}", "existing": True})
            return 0
    if review["comments"]:
        problems = review_lib.anchor_problems(review["comments"], files_of(client, owner, repo, number))
        if problems:
            raise Invalid("GitHub would refuse these inline comments: " + "; ".join(problems))
    payload = {
        "commit_id": sha,
        "body": review["body"].rstrip() + "\n\n" + marker,
        "event": "COMMENT",
        "comments": [dict(comment) for comment in review["comments"]],
    }
    try:
        created = client.request("POST", f"/repos/{owner}/{repo}/pulls/{number}/reviews", body=payload)
    except gh.GitHubHTTPError as exc:
        if exc.status == 422:
            raise Invalid("GitHub refused the review (HTTP 422): check the commit and every comment's line") from exc
        raise
    review_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(review_id, int) or isinstance(review_id, bool):
        gh.fail("GitHub returned a review without an id")
    emit({"url": f"{base}#pullrequestreview-{review_id}", "existing": False})
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="github-review.py", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch")
    fetch.add_argument("--pr", required=True)
    fetch.add_argument("--out", required=True)
    for name in ("check", "publish"):
        sub = commands.add_parser(name)
        sub.add_argument("--pr", required=True)
        sub.add_argument("--head-sha", required=True)
        sub.add_argument("--comments", required=True)
    args = parser.parse_args(argv)
    handler = {"fetch": command_fetch, "check": command_check, "publish": command_publish}[args.command]
    try:
        return handler(args)
    except Invalid as exc:
        emit({"error": gh.redact_text(str(exc))})
        return INVALID_EXIT
    except gh.ScriptFailure as exc:
        sys.stderr.write(f"github-review.py: {gh.redact_text(str(exc))}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
