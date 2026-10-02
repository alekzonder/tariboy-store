#!/usr/bin/env python3
"""Check on implement -> review: the pull_request artifact names an open (or
merged) pull request."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

EXPECTED_FORM = "https://github.com/OWNER/REPO/pull/NUMBER"
SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def main() -> int:
    task = pr_lib.load_task()
    value = pr_lib.artifact(task, "pull_request")
    if value is None:
        return reject(
            "The pull_request artifact is missing. Store the URL of the task's pull "
            f"request in the form {EXPECTED_FORM}, with nothing after the number."
        )
    try:
        owner, repo, number = pr_lib.parse_pull_request_url(value)
    except ValueError:
        return reject(
            "The pull_request artifact is not a GitHub pull request URL. Store it in "
            f"the form {EXPECTED_FORM}, with nothing after the number (no query, "
            "fragment, trailing slash, or newline)."
        )

    name = f"{owner}/{repo}#{number}"
    client = pr_lib.GitHubClient()
    try:
        pull = client.get(f"/repos/{owner}/{repo}/pulls/{number}")
    except pr_lib.GitHubHTTPError as exc:
        if exc.status != 404:
            raise
        return reject(
            f"Pull request {name} does not exist, or the token cannot see it. Store "
            "the URL of the task's own pull request as the pull_request artifact."
        )

    if not isinstance(pull, dict):
        pr_lib.fail("GitHub returned an unexpected pull request response")
    if pull.get("number") != number or isinstance(pull.get("number"), bool):
        pr_lib.fail("GitHub returned the wrong pull request number")
    state = pull.get("state")
    if state not in {"open", "closed"}:
        pr_lib.fail("GitHub pull request has an invalid state")
    merged = pull.get("merged")
    if not isinstance(merged, bool):
        pr_lib.fail("GitHub pull request has an invalid merged flag")
    head = pull.get("head")
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        pr_lib.fail("GitHub pull request has an invalid head SHA")

    if merged:
        pr_lib.write_result(message=f"Pull request {name} is already merged.")
        return 0
    if state == "closed":
        return reject(
            f"Pull request {name} is closed without a merge; reopen it or open a new "
            "one and store its URL as the pull_request artifact."
        )
    pr_lib.write_result(message=f"Pull request {name} is open at {head_sha[:12]}.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
