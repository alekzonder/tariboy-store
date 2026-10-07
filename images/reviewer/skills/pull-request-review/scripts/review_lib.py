#!/usr/bin/env python3
"""The review_comments contract of the pull-request-review utility.

review_comments is one JSON object:

    {
      "body": "Markdown summary of the review",
      "comments": [
        {"path": "src/app.py", "line": 12, "side": "RIGHT", "body": "Markdown"},
        {"path": "src/app.py", "start_line": 3, "line": 5, "body": "Markdown"}
      ]
    }

`side` is RIGHT (the new file, the default) or LEFT (the old file). A comment
may only anchor on a line the pull request's diff shows on that side: GitHub
refuses the whole review otherwise.
"""

from __future__ import annotations

import json
import re
from typing import Any

MAX_COMMENTS = 100
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
SIDES = {"RIGHT", "LEFT"}
COMMENT_FIELDS = {"path", "line", "side", "start_line", "start_side", "body"}


class InvalidReview(ValueError):
    """review_comments breaks the contract; the message says how."""


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def parse_review_comments(text: str | None) -> dict:
    """The parsed review_comments object, or InvalidReview naming the defect."""
    if not text or not text.strip():
        raise InvalidReview("The review_comments artifact is missing or blank.")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidReview(
            f"The review_comments artifact is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(value, dict) or set(value) - {"body", "comments"}:
        raise InvalidReview(
            'The review_comments artifact must be one JSON object with only "body" and "comments".'
        )
    body = value.get("body")
    if not isinstance(body, str) or not body.strip():
        raise InvalidReview('review_comments needs a non-empty "body": the summary of the review.')
    comments = value.get("comments", [])
    if not isinstance(comments, list):
        raise InvalidReview('"comments" in review_comments must be a list.')
    if len(comments) > MAX_COMMENTS:
        raise InvalidReview(f"review_comments holds more than {MAX_COMMENTS} inline comments.")
    for index, comment in enumerate(comments, 1):
        where = f"Comment {index} of review_comments"
        if not isinstance(comment, dict) or set(comment) - COMMENT_FIELDS:
            raise InvalidReview(
                f"{where} must be an object with only path, line, side, start_line, start_side and body."
            )
        if not isinstance(comment.get("path"), str) or not comment["path"]:
            raise InvalidReview(f'{where} needs a "path" of a file the pull request changes.')
        if not _positive_int(comment.get("line")):
            raise InvalidReview(f'{where} needs a positive integer "line".')
        if not isinstance(comment.get("body"), str) or not comment["body"].strip():
            raise InvalidReview(f'{where} needs a non-empty "body".')
        side = comment.get("side", "RIGHT")
        if side not in SIDES:
            raise InvalidReview(f'{where} has "side" other than RIGHT or LEFT.')
        if "start_line" in comment:
            start = comment["start_line"]
            if not _positive_int(start) or start >= comment["line"]:
                raise InvalidReview(f'{where} needs a "start_line" below its "line".')
            if comment.get("start_side", side) != side:
                raise InvalidReview(f"{where} starts and ends on different sides.")
        elif "start_side" in comment:
            raise InvalidReview(f'{where} has "start_side" without "start_line".')
    return {"body": body, "comments": comments}


def diff_lines(patch: str) -> dict[str, set[int]]:
    """The line numbers a unified diff patch shows, per side."""
    lines: dict[str, set[int]] = {"LEFT": set(), "RIGHT": set()}
    old = new = 0
    in_hunk = False
    for row in patch.split("\n"):
        match = HUNK_RE.match(row)
        if match:
            old, new = int(match.group(1)), int(match.group(3))
            in_hunk = True
            continue
        if not in_hunk or not row or row.startswith("\\"):
            continue
        if row.startswith("+"):
            lines["RIGHT"].add(new)
            new += 1
        elif row.startswith("-"):
            lines["LEFT"].add(old)
            old += 1
        elif row.startswith(" "):
            lines["LEFT"].add(old)
            lines["RIGHT"].add(new)
            old += 1
            new += 1
    return lines


def anchor_problems(comments: list[dict], files: list[dict]) -> list[str]:
    """One line per comment that GitHub would refuse, given the pull request's
    files as /pulls/N/files returns them."""
    patches: dict[str, str | None] = {}
    for item in files:
        if isinstance(item, dict) and isinstance(item.get("filename"), str):
            patch = item.get("patch")
            patches[item["filename"]] = patch if isinstance(patch, str) else None
    problems = []
    for index, comment in enumerate(comments, 1):
        path = comment["path"]
        side = comment.get("side", "RIGHT")
        if path not in patches:
            problems.append(f"comment {index}: the pull request does not change {path}")
            continue
        if patches[path] is None:
            problems.append(
                f"comment {index}: GitHub shows no diff for {path}; move the finding into the body"
            )
            continue
        shown = diff_lines(patches[path])[side]
        wanted = [comment["line"]]
        if "start_line" in comment:
            wanted.append(comment["start_line"])
        missing = [line for line in wanted if line not in shown]
        if missing:
            problems.append(
                f"comment {index}: line {missing[0]} of {path} ({side}) is outside the diff"
            )
    return problems


def annotate(patch: str) -> list[str]:
    """The patch with each diff line prefixed by the anchor it takes: `L<old>`
    for a removed line (side LEFT), `R<new>` for an added or context line
    (side RIGHT; a context line is also `L<old>`)."""
    rows = []
    old = new = 0
    in_hunk = False
    for row in patch.split("\n"):
        match = HUNK_RE.match(row)
        if match:
            old, new = int(match.group(1)), int(match.group(3))
            in_hunk = True
            rows.append(row)
            continue
        if not in_hunk or not row:
            continue
        if row.startswith("\\"):
            rows.append(f"{'':>14} {row}")
        elif row.startswith("+"):
            rows.append(f"{'':>6} R{new:<6} {row}")
            new += 1
        elif row.startswith("-"):
            rows.append(f"L{old:<5} {'':>7} {row}")
            old += 1
        elif row.startswith(" "):
            rows.append(f"L{old:<5} R{new:<6} {row}")
            old += 1
            new += 1
    return rows
