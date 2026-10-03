#!/usr/bin/env python3
"""Check on implement -> review: the pull_request artifact names an open (or
merged) pull request, and an open one is the pull request this task's process
asks for: its head branch is the branch artifact, its head commit is the
commit the verification artifact names, its base is the repository's default
branch, and neither its title nor its body names the task key.

Messages name no branch, title or body: those come from GitHub."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

EXPECTED_FORM = "https://github.com/OWNER/REPO/pull/NUMBER"
SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
VERIFIED_SHA_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{64}|[0-9a-f]{40})(?![0-9a-fA-F])")


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def text_or_none(value: object, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        pr_lib.fail(f"GitHub pull request has an invalid {label}")
    return value


def names_key(text: str, key: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", text, re.IGNORECASE))


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

    try:
        branch = pr_lib.validate_branch(pr_lib.artifact(task, "branch"), "task")
    except ValueError:
        return reject(
            "The branch artifact is missing or is not a valid branch name. Store the "
            "name of the task's branch, exactly as git shows it, with nothing around "
            "it, and advance again."
        )
    verification = pr_lib.artifact(task, "verification") or ""
    verified = set(VERIFIED_SHA_RE.findall(verification))
    if not verified:
        return reject(
            "The verification artifact is missing or names no full 40-character "
            "commit SHA. Run the complete verification on the commit you pushed and "
            "store, as Markdown, the command, that commit's full SHA and the result."
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
            f"Pull request {name} is closed without a merge; reopen it, or ask the "
            "customer through the task whether a new pull request replaces it."
        )

    head_ref = head.get("ref")
    if not isinstance(head_ref, str) or not head_ref:
        pr_lib.fail("GitHub pull request has an invalid head branch")
    base = pull.get("base")
    base_ref = base.get("ref") if isinstance(base, dict) else None
    if not isinstance(base_ref, str) or not base_ref:
        pr_lib.fail("GitHub pull request has an invalid base branch")
    title = text_or_none(pull.get("title"), "title")
    body = text_or_none(pull.get("body"), "body")
    repository = client.get(f"/repos/{owner}/{repo}")
    default_branch = repository.get("default_branch") if isinstance(repository, dict) else None
    if not isinstance(default_branch, str) or not default_branch:
        pr_lib.fail("GitHub returned a repository without a default branch")

    if head_ref != branch:
        return reject(
            f"The head branch of pull request {name} is not the branch artifact. "
            "Store the task's own branch as the branch artifact, or open the task's "
            "pull request from that branch, and advance again."
        )
    if base_ref != default_branch:
        return reject(
            f"Pull request {name} does not target the repository's default branch. "
            "Change its base to the default branch and advance again."
        )
    if head_sha not in verified:
        return reject(
            f"The verification artifact does not name the head commit {head_sha[:12]} "
            f"of pull request {name}. Run the complete verification on that commit "
            "and store its full SHA, the command and the result in the verification "
            "artifact; every new head commit needs its own verification."
        )
    key = task.get("key")
    if isinstance(key, str) and key:
        for label, text in (("title", title), ("body", body)):
            if names_key(text, key):
                return reject(
                    f"The {label} of pull request {name} names the task key. Keep the "
                    "task linkage on the task: edit the pull request so its title and "
                    "body are in English without the key, and advance again."
                )

    pr_lib.write_result(message=f"Pull request {name} is open at {head_sha[:12]}.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
