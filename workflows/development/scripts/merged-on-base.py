#!/usr/bin/env python3
"""Check on complete -> done (run as the holder): the merge commit is on the
local base branch, and the task's worktree and local head branch are gone."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
STATE_FILE = "pr-monitor.json"
DEFAULT_BASE = "main"
MAX_GIT_OUTPUT = 1024 * 1024


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def git(*options: str, values: tuple[str, ...] = ()) -> subprocess.CompletedProcess[bytes]:
    """Run git with an argument list: fixed options, then validated values.

    The values follow "--", and none may start with "-", so git can never
    read one as an option."""
    for value in values:
        if not value or value.startswith("-"):
            pr_lib.fail("refusing to pass an option-like value to git")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ["git", *options, *(("--", *values) if values else ())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise pr_lib.ScriptFailure("git is required and must answer within 30 seconds") from exc
    if len(result.stdout) > MAX_GIT_OUTPUT:
        pr_lib.fail("git output exceeded its size limit")
    return result


def state_ref(state: dict, key: str) -> str | None:
    value = state.get(key)
    if value is None:
        return None
    try:
        return pr_lib.validate_branch(value, key)
    except ValueError:
        pr_lib.fail(f"the pull request monitor state has an invalid {key}")


def monitor_state() -> dict:
    task_dir = os.environ.get("TARIBOY_TASK_DIR")
    if not task_dir:
        return {}
    path = Path(task_dir) / STATE_FILE
    try:
        with path.open("rb") as source:
            data = source.read(pr_lib.MAX_RESPONSE_BYTES + 1)
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise pr_lib.ScriptFailure("the pull request monitor state is unreadable") from exc
    if len(data) > pr_lib.MAX_RESPONSE_BYTES:
        pr_lib.fail("the pull request monitor state exceeds its size limit")
    try:
        state = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise pr_lib.ScriptFailure("the pull request monitor state is malformed") from exc
    if not isinstance(state, dict):
        pr_lib.fail("the pull request monitor state has an unexpected shape")
    return state


def worktree_branches() -> list[str]:
    result = git("worktree", "list", "--porcelain", "-z")
    if result.returncode != 0:
        pr_lib.fail("git worktree list failed")
    return [
        field[len(b"branch ") :].decode("utf-8", "replace")
        for field in result.stdout.split(b"\0")
        if field.startswith(b"branch ")
    ]


def main() -> int:
    task = pr_lib.load_task()
    merge_commit = pr_lib.artifact(task, "merge_commit")
    if merge_commit is None or not SHA_RE.fullmatch(merge_commit):
        return reject(
            "The merge_commit artifact is missing or is not a 7 to 40 character "
            "lowercase hexadecimal commit SHA. The pull request monitor records it "
            "when the pull request merges."
        )

    inside = git("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        return reject(
            "The working directory is not inside a Git work tree. Set the working "
            "directory to the repository's main checkout and advance again."
        )

    state = monitor_state()
    base = state_ref(state, "base_ref") or DEFAULT_BASE
    head = state_ref(state, "head_ref")
    base_ref = f"refs/heads/{base}"

    if git("show-ref", "--verify", "--quiet", values=(base_ref,)).returncode != 0:
        return reject(
            f"The local branch {base} does not exist in this repository. Set the "
            "working directory to the repository's main checkout, then fetch and "
            f"fast-forward {base}."
        )

    if git("cat-file", "-e", values=(f"{merge_commit}^{{commit}}",)).returncode != 0:
        return reject(
            f"The merge commit {merge_commit} is not in this repository; fetch and "
            f"fast-forward {base} first."
        )
    ancestor = git("merge-base", "--is-ancestor", values=(merge_commit, base_ref))
    if ancestor.returncode == 1:
        return reject(
            f"The merge commit {merge_commit} is not on the local branch {base}; "
            f"fast-forward {base} first. Never reset or force it."
        )
    if ancestor.returncode != 0:
        pr_lib.fail("git merge-base failed")

    if head is not None:
        head_ref = f"refs/heads/{head}"
        if head_ref in worktree_branches():
            return reject(
                "A worktree of this repository still has the pull request's head "
                "branch checked out. Remove that worktree (git worktree list shows "
                "it) and advance again."
            )
        if git("show-ref", "--verify", "--quiet", values=(head_ref,)).returncode == 0:
            return reject(
                "The pull request's head branch still exists as a local branch. "
                "Delete that local branch and advance again."
            )

    pr_lib.write_result(message=f"Merge commit {merge_commit} is on the local branch {base}.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
