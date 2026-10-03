#!/usr/bin/env python3
"""Check on plan -> approval: the plan artifact is Markdown with the four
sections the plan status asks for, each with text of its own.

A section is a Markdown heading (any level, outside code fences) whose text
starts with one of the section's names, in English or Russian. Its text is
every non-blank line up to the next heading of the same or a higher level, so
subsections count. The check proves the plan has its parts; whether they are
good is the customer's decision in the approval status."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

SECTIONS = (
    ("How it works", ("how it works", "how the solution works", "как работает", "как это работает")),
    ("Steps", ("steps", "implementation steps", "шаги", "шаги реализации")),
    ("Verification", ("verification", "проверка")),
    ("Limitations", ("limitations", "ограничения")),
)
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def outline(plan: str) -> list[tuple[int, str, bool]]:
    """(level, heading text, has text) for every heading outside a code fence.
    A line of level 0 marks text that belongs to the enclosing headings."""
    lines: list[tuple[int, str]] = []
    fence: str | None = None
    for raw in plan.splitlines():
        marker = FENCE_RE.match(raw)
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            lines.append((0, "text"))
            continue
        if marker:
            fence = marker.group(1)
            lines.append((0, "text"))
            continue
        heading = HEADING_RE.match(raw)
        if heading:
            lines.append((len(heading.group(1)), heading.group(2).strip()))
        elif raw.strip():
            lines.append((0, "text"))

    headings = []
    for index, (level, text) in enumerate(lines):
        if level == 0:
            continue
        has_text = False
        for next_level, _ in lines[index + 1 :]:
            if next_level and next_level <= level:
                break
            if next_level == 0:
                has_text = True
                break
        headings.append((level, text, has_text))
    return headings


def section_state(headings: list[tuple[int, str, bool]], names: tuple[str, ...]) -> str:
    """"ok", "empty" (heading without text) or "missing"."""
    state = "missing"
    for _, text, has_text in headings:
        if any(text.casefold().startswith(name) for name in names):
            if has_text:
                return "ok"
            state = "empty"
    return state


def main() -> int:
    task = pr_lib.load_task()
    plan = pr_lib.artifact(task, "plan")
    if plan is None or not plan.strip():
        return reject(
            "The plan artifact is missing or empty. Store the whole plan, as Markdown, "
            "in the plan artifact and advance again."
        )

    headings = outline(plan)
    missing, empty = [], []
    for title, names in SECTIONS:
        state = section_state(headings, names)
        if state == "missing":
            missing.append(title)
        elif state == "empty":
            empty.append(title)
    if missing or empty:
        problems = []
        if missing:
            problems.append("it has no section " + ", ".join(f"'{name}'" for name in missing))
        if empty:
            problems.append("these sections have no text: " + ", ".join(f"'{name}'" for name in empty))
        return reject(
            "The plan artifact is incomplete: "
            + "; ".join(problems)
            + ". Give the plan a Markdown heading for each of 'How it works', 'Steps', "
            "'Verification' and 'Limitations' (or 'Как работает', 'Шаги', 'Проверка', "
            "'Ограничения'), each followed by its text, store the whole plan again and "
            "advance again."
        )

    pr_lib.write_result(message="The plan has all four sections.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
