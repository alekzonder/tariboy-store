#!/usr/bin/env python3
"""Check on every outcome of triage: the triage artifact is a record of
"Key: value" lines, and it supports the outcome the agent asks for.

Keys (case-insensitive), one per line:

- Decision: needs_approval, autonomous or close. It must equal the outcome.
- Route: improve, tariboyd or other. Only the improve route continues.
- Duplicate: none, or the key of the task this one repeats.
- Rule: for autonomous, the clause of the autonomous-change rule that applies.
- Version: for autonomous, patch. A change that needs a minor or major
  version is outside the rule.
- Closed as: for close, duplicate, wrong_route or noise.
- Reason: for close, why the task closes.

needs_approval also needs a plan artifact with the four sections of the plan
status. The check proves the record has its parts and agrees with the outcome;
whether the decision is right is the agent's judgment, and the customer sees
the plan in approval."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

OUTCOMES = {"needs_approval", "autonomous", "close"}
ROUTES = {"improve", "tariboyd", "other"}
CLOSED_AS = {"duplicate", "wrong_route", "noise"}
# Words that tie the Rule line to the clauses of the autonomous-change rule:
# it clarifies or tightens an existing rule, is covered by a new eval, leaves
# ROLE.md, the skills and the plugins alone, and needs no minor version.
RULE_CLAUSE_RE = re.compile(
    r"уточня|ужесточа|clarif|tighten|eval|ROLE\.md|скил|skill|plugin|плагин|minor|минор",
    re.IGNORECASE,
)
MIN_TEXT = 20
LINE_RE = re.compile(r"^\s*[-*]?\s*([A-Za-z][A-Za-z ]{1,20}?)\s*:\s*(.*?)\s*$")
TASK_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*-[A-Za-z0-9]+$")

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


def parse_record(text: str) -> dict[str, str]:
    record: dict[str, str] = {}
    for raw in text.splitlines():
        match = LINE_RE.match(raw)
        if match:
            key = " ".join(match.group(1).lower().split())
            record.setdefault(key, match.group(2))
    return record


def outline(plan: str) -> list[tuple[int, str, bool]]:
    """(level, heading text, has text) for every heading outside a code fence."""
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


def plan_problems(plan: str | None) -> str | None:
    if plan is None or not plan.strip():
        return (
            "The plan artifact is missing or empty. Store the whole plan, as Markdown, "
            "in the plan artifact and advance again."
        )
    headings = outline(plan)
    bad = []
    for title, names in SECTIONS:
        state = "missing"
        for _, text, has_text in headings:
            if any(text.casefold().startswith(name) for name in names):
                if has_text:
                    state = "ok"
                    break
                state = "empty"
        if state != "ok":
            bad.append(f"'{title}' is {state}")
    if bad:
        return (
            "The plan artifact is incomplete: " + "; ".join(bad) + ". Give the plan a "
            "Markdown heading for each of 'How it works', 'Steps', 'Verification' and "
            "'Limitations' (or 'Как работает', 'Шаги', 'Проверка', 'Ограничения'), each "
            "followed by its text, store the whole plan again and advance again."
        )
    return None


def requested_outcome(task: dict) -> str:
    value = os.environ.get("TARIBOY_WORKFLOW_OUTCOME") or task.get("outcome")
    return value if isinstance(value, str) else ""


def main() -> int:
    task = pr_lib.load_task()
    outcome = requested_outcome(task)
    if outcome not in OUTCOMES:
        pr_lib.fail("the requested outcome is not a triage outcome")
    text = pr_lib.artifact(task, "triage")
    if text is None or not text.strip():
        return reject(
            "The triage artifact is missing or empty. Store the triage record as lines "
            "'Decision:', 'Route:', 'Duplicate:' and the lines your decision needs, and "
            "advance again."
        )
    record = parse_record(text)

    decision = record.get("decision", "").lower()
    if decision != outcome:
        return reject(
            f"The Decision line of the triage record is '{decision or 'missing'}', but you "
            f"advance with the outcome {outcome}. Make them agree, or choose the right "
            "outcome, and advance again."
        )

    route = record.get("route", "").lower()
    duplicate = record.get("duplicate", "")
    if outcome != "close":
        if route != "improve":
            return reject(
                "The Route line must be 'improve' to continue; a task of another route "
                "closes with the outcome close and 'Closed as: wrong_route'."
            )
        if duplicate.lower() != "none":
            return reject(
                "The Duplicate line must be 'none' to continue; a task that repeats "
                "another closes with the outcome close and 'Closed as: duplicate'."
            )

    if outcome == "autonomous":
        rule = record.get("rule", "")
        if len(rule) < MIN_TEXT or not RULE_CLAUSE_RE.search(rule):
            return reject(
                "The Rule line must quote the clause of the autonomous-change rule that "
                "applies, and say how the change meets it: it clarifies or tightens an "
                "existing rule, is covered by a new eval, leaves ROLE.md, the skills and "
                "the plugins alone, and needs no minor version."
            )
        if record.get("version", "").lower() != "patch":
            return reject(
                "The Version line must be 'patch': a change that needs a minor or major "
                "version is outside the rule and needs approval. Use the outcome "
                "needs_approval with a plan."
            )
    elif outcome == "needs_approval":
        problem = plan_problems(pr_lib.artifact(task, "plan"))
        if problem:
            return reject(problem)
    else:
        closed_as = record.get("closed as", "").lower()
        if closed_as not in CLOSED_AS:
            return reject(
                "The 'Closed as' line must be one of duplicate, wrong_route or noise."
            )
        if closed_as == "duplicate" and (duplicate.lower() == "none" or not TASK_KEY_RE.match(duplicate.split()[0] if duplicate.split() else "")):
            return reject(
                "A duplicate closes with the key of the task it repeats on the "
                "'Duplicate' line, for example 'Duplicate: IMPROVE-abcd'."
            )
        if len(record.get("reason", "")) < MIN_TEXT:
            return reject(
                "The Reason line must say why the task closes, in at least a full sentence."
            )

    pr_lib.write_result(message=f"The triage record supports the outcome {outcome}.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
