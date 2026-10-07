#!/usr/bin/env python3
"""Check on review -> approval (`findings`) and review -> approval_clean
(`no_findings`): the review covers the pull request's current head commit,
and with findings, review_comments is a review GitHub will accept.

Messages name no title, body or comment text: those come from the agent and
from GitHub."""

from __future__ import annotations

from pathlib import Path
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402
import review_lib  # noqa: E402

EXPECTED_FORM = "https://github.com/OWNER/REPO/pull/NUMBER"
SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def main() -> int:
    task = pr_lib.load_task()
    outcome = os.environ.get("TARIBOY_WORKFLOW_OUTCOME") or task.get("outcome")
    try:
        owner, repo, number = pr_lib.parse_pull_request_url(pr_lib.artifact(task, "pull_request"))
    except ValueError:
        return reject(
            "The pull_request artifact is not a GitHub pull request URL in the form "
            f"{EXPECTED_FORM}. Leave it as the task was created with it."
        )
    head_sha = pr_lib.artifact(task, "head_sha") or ""
    if not SHA_RE.fullmatch(head_sha):
        return reject(
            "The head_sha artifact must be the full 40-character SHA of the head commit "
            "you reviewed, with nothing around it. Store it as the VALUE argument."
        )
    if not (pr_lib.artifact(task, "review") or "").strip():
        return reject("The review artifact is blank. Store the review as Markdown from standard input.")

    review = None
    if outcome == "findings":
        try:
            review = review_lib.parse_review_comments(pr_lib.artifact(task, "review_comments"))
        except review_lib.InvalidReview as exc:
            return reject(f"{exc} Fix review_comments and advance again.")

    name = f"{owner}/{repo}#{number}"
    client = pr_lib.GitHubClient()
    try:
        pull = client.get(f"/repos/{owner}/{repo}/pulls/{number}")
    except pr_lib.GitHubHTTPError as exc:
        if exc.status != 404:
            raise
        return reject(f"Pull request {name} does not exist, or the token cannot see it.")
    head = pull.get("head") if isinstance(pull, dict) else None
    current = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(current, str) or not SHA_RE.fullmatch(current):
        pr_lib.fail("GitHub pull request has an invalid head SHA")
    if current != head_sha:
        return reject(
            f"Pull request {name} moved: its head is now {current}, not the reviewed "
            f"{head_sha[:12]}. Review the new head, store its SHA in head_sha, and advance again."
        )

    if review is not None and review["comments"]:
        files = client.paginate(f"/repos/{owner}/{repo}/pulls/{number}/files", limit=3000)
        problems = review_lib.anchor_problems(review["comments"], files)
        if problems:
            listed = "; ".join(problems[:10])
            more = f"; and {len(problems) - 10} more" if len(problems) > 10 else ""
            return reject(
                "GitHub would refuse these inline comments: "
                f"{listed}{more}. Anchor each one on a line the diff shows on its side, "
                "or move it into the body, and advance again."
            )

    count = len(review["comments"]) if review is not None else 0
    pr_lib.write_result(message=f"The review covers {name} at {head_sha[:12]} with {count} inline comments.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
