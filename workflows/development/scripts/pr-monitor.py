#!/usr/bin/env python3
"""Watch script of the review status: reports `merged` when the task's pull
request merged, `changes_requested` when something on it needs the developer,
and stays quiet otherwise.

Each run observes the pull request completely (the pull request, check runs
and commit statuses of its head, reviews, review comments, and issue
comments) before it decides; any incomplete or malformed answer is a failure,
and the state file is left as it was. The state file,
TARIBOY_TASK_DIR/pr-monitor.json, holds the identities of the items already
handed to the developer (`acknowledged`) and the items of the last reported
outcome (`pending`, keyed by the visit that reported them).

Text taken from GitHub is untrusted: no body is ever read into the message or
the state file; a message line carries only the item kind, the author login
or check name, a URL, and a state. Odd values never stop the watch: an
unusable login reads `unknown`, and control and separator characters in a
check name or status context become spaces.

The whole run has a 50-second deadline, below the 60-second watch timeout,
so a slow GitHub is a failure that leaves the state file as it was.

One window remains. The state file is written before the result file, so a
run killed in the milliseconds between the two writes leaves a pending entry
that the daemon never applied. The same visit reports it again; but if the
task leaves the status by another route first (an operator move), a later
visit treats that entry as applied and acknowledges its items, which the
developer then never saw in a transition message.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
from typing import Any
import unicodedata

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402
from pr_lib import fail  # noqa: E402

STATE_FILE = "pr-monitor.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}(\[bot\])?$")
UNKNOWN_LOGIN = "unknown"
STRIPPED_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}
RUN_DEADLINE_SECONDS = 50
URL_RE = re.compile(r"^https://[A-Za-z0-9._~:/?#@!&*+,;=%-]+$")
FAILED_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
FAILED_STATES = {"failure", "error"}
MAX_LISTED = 20
MESSAGE_BUDGET_BYTES = 3900
MAX_NAME_CHARS = 100
MAX_URL_CHARS = 300
IDENTITY_HASH_CHARS = 16


# --- Field validation (from the github-pr-workflow utility) ------------------


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
    if (
        not isinstance(item, str)
        or pr_lib.CONTROL_RE.search(item)
        or len(item) > pr_lib.MAX_RESPONSE_BYTES
    ):
        fail(f"GitHub {label} has an invalid {key}")
    return pr_lib.redact_text(item)


def nonempty_text_field(value: dict[str, Any], key: str, label: str) -> str:
    item = text_field(value, key, label)
    if not item:
        fail(f"GitHub {label} has an invalid {key}")
    return item


def body_is_empty(value: dict[str, Any], label: str) -> bool:
    """Validate a body without keeping it: only its emptiness is used."""
    if "body" not in value:
        fail(f"GitHub {label} is missing body")
    body = value["body"]
    if body is None:
        return True
    if not isinstance(body, str) or "\x00" in body or len(body) > pr_lib.MAX_RESPONSE_BYTES:
        fail(f"GitHub {label} has an invalid body")
    return not body.strip()


def login_of(value: dict[str, Any]) -> str | None:
    """The author login, or None when it is missing or unusable."""
    user = value.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    if not isinstance(login, str) or not LOGIN_RE.fullmatch(login):
        return None
    return pr_lib.redact_text(login)


def label_field(value: dict[str, Any], key: str, label: str) -> str:
    """A check name or status context: control, format, and separator
    characters become spaces instead of failing the run."""
    item = value.get(key)
    if not isinstance(item, str) or len(item) > pr_lib.MAX_RESPONSE_BYTES:
        fail(f"GitHub {label} has an invalid {key}")
    cleaned = "".join(
        " " if unicodedata.category(character) in STRIPPED_CATEGORIES else character
        for character in item
    )
    return pr_lib.redact_text(cleaned.strip())


def url_field(value: dict[str, Any], key: str, fallback: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        return fallback
    return fact_url(pr_lib.redact_text(item), fallback)


def unique_id(item: dict[str, Any], label: str, seen: set[int]) -> int:
    object_id = integer_field(item, "id", label)
    if object_id in seen:
        fail(f"GitHub returned duplicate {label} IDs")
    seen.add(object_id)
    return object_id


# --- Message facts -----------------------------------------------------------


def fact_url(value: str | None, fallback: str) -> str:
    if value and len(value) <= MAX_URL_CHARS and URL_RE.fullmatch(value):
        return value
    return fallback


def fact_name(value: str) -> str:
    return value[:MAX_NAME_CHARS]


def identity_name(value: str) -> str:
    """A name as it appears in an identity: long names by a hash prefix."""
    if len(value) <= MAX_NAME_CHARS:
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:IDENTITY_HASH_CHARS]


def make_item(identity: str, kind: str, name: str, url: str, state: str) -> dict[str, str]:
    return {"id": identity, "kind": kind, "name": name, "url": url, "state": state}


# --- Observation -------------------------------------------------------------


def normalize_pr(value: Any, number: int) -> dict[str, Any]:
    item = require_dict(value, "pull request")
    if integer_field(item, "number", "pull request") != number:
        fail("GitHub returned the wrong pull request number")
    state = text_field(item, "state", "pull request")
    if state not in {"open", "closed"}:
        fail("GitHub pull request has an invalid state")
    merged = item.get("merged")
    if not isinstance(merged, bool):
        fail("GitHub pull request has an invalid merged flag")
    merge_sha = None
    if merged:
        merge_sha = item.get("merge_commit_sha")
        if not isinstance(merge_sha, str) or not SHA_RE.fullmatch(merge_sha):
            fail("merged pull request is missing a valid merge commit SHA")
    closed_at = None
    if state == "closed" and not merged:
        closed_at = nonempty_text_field(item, "closed_at", "pull request")
    head = require_dict(item.get("head"), "pull request head")
    head_sha = head.get("sha")
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        fail("GitHub pull request has an invalid head SHA")
    base = require_dict(item.get("base"), "pull request base")
    try:
        head_ref = pr_lib.validate_branch(head.get("ref"), "head")
        base_ref = pr_lib.validate_branch(base.get("ref"), "base")
    except ValueError as exc:
        raise pr_lib.ScriptFailure(f"GitHub pull request has an {exc}") from exc
    return {
        "state": state,
        "merged": merged,
        "merge_commit_sha": merge_sha,
        "closed_at": closed_at,
        "head_sha": head_sha,
        "head_ref": head_ref,
        "base_ref": base_ref,
        "author": login_of(item),
    }


def failed_checks(values: list[Any], head_sha: str, pr_url: str) -> list[dict[str, str]]:
    items = []
    seen: set[int] = set()
    for value in values:
        check = require_dict(value, "check run")
        check_id = unique_id(check, "check run", seen)
        name = label_field(check, "name", "check run")
        status = nonempty_text_field(check, "status", "check run")
        conclusion = text_field(check, "conclusion", "check run", nullable=True)
        if status != "completed" or conclusion not in FAILED_CONCLUSIONS:
            continue
        label = name or str(check_id)
        items.append(
            make_item(
                f"check:{head_sha}:{identity_name(label)}:{check_id}",
                "check",
                fact_name(label),
                url_field(check, "html_url", pr_url),
                conclusion,
            )
        )
    return sorted(items, key=lambda item: item["id"])


def failed_statuses(values: list[Any], head_sha: str, pr_url: str) -> list[dict[str, str]]:
    newest: dict[str, tuple[int, str, str]] = {}
    seen: set[int] = set()
    for value in values:
        status = require_dict(value, "commit status")
        status_id = unique_id(status, "commit status", seen)
        context = label_field(status, "context", "commit status") or str(status_id)
        state = nonempty_text_field(status, "state", "commit status")
        url = url_field(status, "target_url", pr_url)
        if context not in newest or newest[context][0] < status_id:
            newest[context] = (status_id, state, url)
    items = [
        make_item(
            f"status:{head_sha}:{identity_name(context)}:{status_id}",
            "status",
            fact_name(context),
            url,
            state,
        )
        for context, (status_id, state, url) in newest.items()
        if state in FAILED_STATES
    ]
    return sorted(items, key=lambda item: item["id"])


def review_items(values: list[Any], author: str | None, pr_url: str) -> list[dict[str, str]]:
    items = []
    seen: set[int] = set()
    for value in values:
        review = require_dict(value, "review")
        review_id = unique_id(review, "review", seen)
        state = nonempty_text_field(review, "state", "review")
        empty = body_is_empty(review, "review")
        if state == "PENDING" and review.get("submitted_at") is None:
            continue
        login = login_of(review)
        by_author = login is not None and login == author
        if state == "CHANGES_REQUESTED" or (state == "COMMENTED" and not empty and not by_author):
            url = url_field(review, "html_url", pr_url)
            name = login or UNKNOWN_LOGIN
            items.append((review_id, make_item(f"review:{review_id}", "review", name, url, state)))
    return [item for _, item in sorted(items, key=lambda pair: pair[0])]


def comment_items(
    values: list[Any], kind: str, author: str | None, pr_url: str
) -> list[dict[str, str]]:
    label = kind.replace("_", " ")
    items = []
    seen: set[int] = set()
    for value in values:
        comment = require_dict(value, label)
        comment_id = unique_id(comment, label, seen)
        login = login_of(comment)
        if login is not None and login == author:
            continue
        url = url_field(comment, "html_url", pr_url)
        name = login or UNKNOWN_LOGIN
        items.append((comment_id, make_item(f"{kind}:{comment_id}", kind, name, url, "new")))
    return [item for _, item in sorted(items, key=lambda pair: pair[0])]


def observe(
    client: pr_lib.GitHubClient, owner: str, repo: str, number: int, pr_url: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    root = f"/repos/{owner}/{repo}"
    pr = normalize_pr(client.get(f"{root}/pulls/{number}"), number)
    head = pr["head_sha"]
    checks = client.paginated_check_runs(f"{root}/commits/{head}/check-runs")
    statuses = client.paginate(f"{root}/commits/{head}/statuses")
    reviews = client.paginate(f"{root}/pulls/{number}/reviews")
    review_comments = client.paginate(f"{root}/pulls/{number}/comments")
    issue_comments = client.paginate(f"{root}/issues/{number}/comments")

    items: list[dict[str, str]] = []
    if pr["closed_at"] is not None:
        items.append(
            make_item(
                f"closed:{pr['closed_at']}",
                "closed",
                f"{owner}/{repo}#{number}",
                pr_url,
                "closed without merge",
            )
        )
    items.extend(failed_checks(checks, head, pr_url))
    items.extend(failed_statuses(statuses, head, pr_url))
    items.extend(review_items(reviews, pr["author"], pr_url))
    items.extend(comment_items(review_comments, "review_comment", pr["author"], pr_url))
    items.extend(comment_items(issue_comments, "issue_comment", pr["author"], pr_url))
    return pr, items


# --- State -------------------------------------------------------------------


def valid_item(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(key), str) for key in ("id", "kind", "name", "url", "state")
    )


def load_state(path: Path) -> dict[str, Any] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise pr_lib.ScriptFailure("the monitor state is unreadable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        fail("the monitor state must be a regular file")
    if info.st_size > pr_lib.MAX_RESPONSE_BYTES:
        fail("the monitor state exceeds its size limit")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise pr_lib.ScriptFailure("the monitor state is unreadable or malformed") from exc
    if not isinstance(state, dict):
        fail("the monitor state has an unexpected shape")
    number = state.get("number")
    acknowledged = state.get("acknowledged")
    pending = state.get("pending")
    if (
        not isinstance(state.get("repo"), str)
        or isinstance(number, bool)
        or not isinstance(number, int)
        or not isinstance(acknowledged, list)
        or not all(isinstance(item, str) for item in acknowledged)
    ):
        fail("the monitor state has an unexpected shape")
    if pending is not None:
        visit_id = pending.get("visit_id") if isinstance(pending, dict) else None
        items = pending.get("items") if isinstance(pending, dict) else None
        if (
            isinstance(visit_id, bool)
            or not isinstance(visit_id, int)
            or not isinstance(items, list)
            or not all(valid_item(item) for item in items)
        ):
            fail("the monitor state has an invalid pending entry")
    return state


def atomic_write(path: Path, payload: bytes) -> None:
    descriptor = -1
    temporary = ""
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = ""
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(path.parent, flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise pr_lib.ScriptFailure("failed to atomically update the monitor state") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def remove_stale_temporaries(directory: Path) -> None:
    """Remove temporary state files a killed run left behind."""
    for path in directory.glob(f".{STATE_FILE}.*.tmp"):
        try:
            path.unlink()
        except OSError:
            pass


def current_head_only(acknowledged: list[str], head_sha: str) -> list[str]:
    """Drop check and status identities of heads other than the current one."""
    kept = []
    for identity in acknowledged:
        kind, _, rest = identity.partition(":")
        if kind in {"check", "status"} and rest.partition(":")[0] != head_sha:
            continue
        kept.append(identity)
    return kept


def write_state(path: Path, state: dict[str, Any]) -> None:
    state = {**state, "acknowledged": current_head_only(state["acknowledged"], state["head_sha"])}
    payload = (
        json.dumps(pr_lib.redact_value(state), sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(payload) > pr_lib.MAX_RESPONSE_BYTES:
        fail("the monitor state exceeds its size limit")
    atomic_write(path, payload)


# --- Decision ----------------------------------------------------------------


def visit_id_of(task: dict) -> int:
    visit = task.get("visit")
    visit_id = visit.get("id") if isinstance(visit, dict) else None
    if isinstance(visit_id, bool) or not isinstance(visit_id, int):
        fail("the task snapshot has no valid visit id")
    return visit_id


def changes_message(name: str, items: list[dict[str, str]]) -> str:
    count = len(items)
    lines = [f"Pull request {name} needs changes ({count} item{'' if count == 1 else 's'}):"]
    size = len(lines[0].encode("utf-8"))
    listed = 0
    for item in items[:MAX_LISTED]:
        line = f"{item['kind']} — {item['name']} — {item['url']} — {item['state']}"
        line_size = len(line.encode("utf-8"))
        if size + 1 + line_size > MESSAGE_BUDGET_BYTES:
            break
        lines.append(line)
        size += 1 + line_size
        listed += 1
    if listed < count:
        lines.append(f"(+{count - listed} more)")
    return "\n".join(lines)


def main() -> int:
    deadline = time.monotonic() + RUN_DEADLINE_SECONDS
    task = pr_lib.load_task()
    visit_id = visit_id_of(task)
    value = pr_lib.artifact(task, "pull_request")
    if value is None:
        fail("the pull_request artifact is missing")
    try:
        owner, repo, number = pr_lib.parse_pull_request_url(value)
    except ValueError as exc:
        raise pr_lib.ScriptFailure("the pull_request artifact is not a GitHub pull request URL") from exc
    task_dir = os.environ.get("TARIBOY_TASK_DIR")
    if not task_dir:
        fail("TARIBOY_TASK_DIR is not set")
    state_path = Path(task_dir) / STATE_FILE
    repository = f"{owner}/{repo}"
    name = f"{repository}#{number}"
    pr_url = f"{pr_lib.PULL_REQUEST_PREFIX}{repository}/pull/{number}"

    remove_stale_temporaries(state_path.parent)
    old = load_state(state_path)
    client = pr_lib.GitHubClient(deadline=deadline)
    pr, observed = observe(client, owner, repo, number, pr_url)
    if time.monotonic() > deadline:
        fail("the run exceeded its overall time limit")

    # Reconcile with the visit: a pending entry of another visit was applied,
    # one of this visit was not (the daemon stopped before recording it).
    acknowledged: list[str] = []
    replay: list[dict[str, str]] = []
    acknowledged_changed = False
    if old is not None and old["repo"] == repository and old["number"] == number:
        acknowledged = list(old["acknowledged"])
        pending = old.get("pending")
        if pending is not None and pending["visit_id"] != visit_id:
            known = set(acknowledged)
            for item in pending["items"]:
                # A close without a merge is a standing condition: it is
                # reported again in every visit while it holds.
                if item["kind"] != "closed" and item["id"] not in known:
                    acknowledged.append(item["id"])
                    known.add(item["id"])
            acknowledged_changed = True
        elif pending is not None:
            replay = list(pending["items"])

    state: dict[str, Any] = {
        "repo": repository,
        "number": number,
        "base_ref": pr["base_ref"],
        "head_ref": pr["head_ref"],
        "head_sha": pr["head_sha"],
        "acknowledged": acknowledged,
        "pending": None,
    }

    if pr["merged"]:
        merge_sha = pr["merge_commit_sha"]
        write_state(state_path, state)
        pr_lib.write_result(
            outcome="merged",
            message=f"Pull request {name} merged as {merge_sha[:12]} into {pr['base_ref']}.",
            artifacts={"merge_commit": merge_sha},
        )
        return 0

    known = set(acknowledged)
    report = list(replay)
    reported = {item["id"] for item in report}
    for item in observed:
        if item["id"] not in known and item["id"] not in reported:
            report.append(item)
            reported.add(item["id"])

    if report:
        state["pending"] = {"visit_id": visit_id, "items": report}
        write_state(state_path, state)
        pr_lib.write_result(outcome="changes_requested", message=changes_message(name, report))
        return 0

    if acknowledged_changed:
        write_state(state_path, state)
    return pr_lib.QUIET_EXIT


if __name__ == "__main__":
    pr_lib.run(main)
