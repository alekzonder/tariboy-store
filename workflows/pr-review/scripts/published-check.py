#!/usr/bin/env python3
"""Check on publish -> done: published_review is the URL of a review that
exists on the task's pull request, on the reviewed head commit, and carries
every inline comment of review_comments.

Messages name no review or comment text: those come from GitHub."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402
import review_lib  # noqa: E402

REVIEW_URL_RE = re.compile(r"^(https://github\.com/[^#]+)#pullrequestreview-([1-9][0-9]{0,19})$")
EXPECTED_FORM = "https://github.com/OWNER/REPO/pull/NUMBER#pullrequestreview-ID"


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def main() -> int:
    task = pr_lib.load_task()
    try:
        owner, repo, number = pr_lib.parse_pull_request_url(pr_lib.artifact(task, "pull_request"))
    except ValueError:
        return reject("The pull_request artifact is not a GitHub pull request URL.")
    value = pr_lib.artifact(task, "published_review") or ""
    match = REVIEW_URL_RE.fullmatch(value)
    if not match:
        return reject(
            f"The published_review artifact must be the review's URL in the form {EXPECTED_FORM}, "
            "exactly as the publish utility printed it. Store it as the VALUE argument."
        )
    if match.group(1) != f"https://github.com/{owner}/{repo}/pull/{number}":
        return reject("The published_review URL belongs to another pull request than pull_request.")
    review_id = match.group(2)
    try:
        expected = review_lib.parse_review_comments(pr_lib.artifact(task, "review_comments"))
    except review_lib.InvalidReview as exc:
        return reject(f"{exc} The published review must be the approved review_comments.")

    name = f"{owner}/{repo}#{number}"
    client = pr_lib.GitHubClient()
    try:
        review = client.get(f"/repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}")
    except pr_lib.GitHubHTTPError as exc:
        if exc.status != 404:
            raise
        return reject(f"Review {review_id} does not exist on pull request {name}. Publish it, then advance again.")
    if not isinstance(review, dict) or str(review.get("id")) != review_id:
        pr_lib.fail("GitHub returned an unexpected review")
    if review.get("state") == "PENDING":
        return reject(f"Review {review_id} on {name} is still pending: submit it, then advance again.")
    head_sha = pr_lib.artifact(task, "head_sha") or ""
    if review.get("commit_id") != head_sha:
        return reject(
            f"Review {review_id} on {name} is not on the reviewed head commit {head_sha[:12]}. "
            "Publish the approved review on that commit."
        )
    comments = client.paginate(f"/repos/{owner}/{repo}/pulls/{number}/reviews/{review_id}/comments", limit=1000)
    if len(comments) < len(expected["comments"]):
        return reject(
            f"Review {review_id} on {name} carries {len(comments)} inline comments, "
            f"review_comments has {len(expected['comments'])}. Publish the whole approved review."
        )
    pr_lib.write_result(message=f"Review {review_id} is published on {name}.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
