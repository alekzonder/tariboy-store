#!/usr/bin/env python3
"""Check on implement -> deliver: the evals artifact proves the change was
evaluated before the pull request.

The artifact is one JSON object:

    {"model": "claude-sonnet-5-5", "cost_usd": 1.25,
     "scenarios": [{"id": "wait-object",
                    "base": {"passed": 0, "of": 3},
                    "new": {"passed": 3, "of": 3}}]}

Every new or changed scenario has its id, the result of the base (before the
change) and the result of the new (after it). Each result is the number of
passed runs and the number of runs, at least 3 runs. The new result passes at
least 2 of 3 (the same ratio for more runs) and is not worse than the base.
A change with no new or changed scenario, for example one that only fixes a
typo, says so with {"not_applicable": "reason"} instead of "scenarios"; the
reason is plain text of at least 20 characters. The model and the cost are
required in both forms, so the run can be repeated and its price is known.

The check proves the evidence has its parts and its numbers agree; running the
evals honestly is the agent's work and the customer reads the numbers in the
pull request."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pr_lib  # noqa: E402

MIN_RUNS = 3
MIN_REASON = 20


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def result_problem(label: str, scenario: str, value: object) -> str | None:
    if not isinstance(value, dict):
        return f"scenario '{scenario}' has no {label} result with 'passed' and 'of'"
    passed, runs = value.get("passed"), value.get("of")
    if not is_int(passed) or not is_int(runs):
        return f"scenario '{scenario}': {label} 'passed' and 'of' must be whole numbers"
    if runs < MIN_RUNS:
        return f"scenario '{scenario}': {label} has {runs} runs; at least {MIN_RUNS} are needed"
    if not 0 <= passed <= runs:
        return f"scenario '{scenario}': {label} 'passed' is outside 0..'of'"
    return None


def main() -> int:
    task = pr_lib.load_task()
    text = pr_lib.artifact(task, "evals")
    if text is None or not text.strip():
        return reject(
            "The evals artifact is missing or empty. Run the evals for every new or "
            "changed scenario on the base and on the change, store the result as JSON "
            "in the evals artifact (see the implement status) and advance again."
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return reject("The evals artifact is not valid JSON. Store one JSON object and advance again.")
    if not isinstance(data, dict):
        return reject("The evals artifact must be one JSON object.")

    model = data.get("model")
    if not isinstance(model, str) or not model.strip():
        return reject("The evals artifact has no 'model': name the pinned model of the runs.")
    cost = data.get("cost_usd")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
        return reject("The evals artifact has no 'cost_usd': give the actual cost as a number, 0 if none.")

    scenarios = data.get("scenarios")
    reason = data.get("not_applicable")
    if scenarios is None:
        if isinstance(reason, str) and len(reason.strip()) >= MIN_REASON:
            pr_lib.write_result(message="The change has no new or changed scenario; the reason is recorded.")
            return 0
        return reject(
            "The evals artifact has no 'scenarios'. List base and new for every new or "
            "changed scenario, or set 'not_applicable' to the reason that none changed."
        )
    if reason is not None:
        return reject("Give either 'scenarios' or 'not_applicable', not both.")
    if not isinstance(scenarios, list) or not scenarios:
        return reject("'scenarios' must be a non-empty list.")

    seen: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str) or not scenario["id"].strip():
            return reject("Every scenario needs a non-empty 'id'.")
        name = scenario["id"]
        if name in seen:
            return reject(f"Scenario '{name}' appears twice.")
        seen.add(name)
        for label in ("base", "new"):
            problem = result_problem(label, name, scenario.get(label))
            if problem:
                return reject(problem[0].upper() + problem[1:] + ".")
        base, new = scenario["base"], scenario["new"]
        if new["passed"] * MIN_RUNS < 2 * new["of"]:
            return reject(
                f"Scenario '{name}': new passes {new['passed']} of {new['of']} runs; at "
                "least 2 of 3 are needed. Fix the change or the scenario and rerun."
            )
        if new["passed"] * base["of"] < base["passed"] * new["of"]:
            return reject(
                f"Scenario '{name}': new ({new['passed']}/{new['of']}) is worse than base "
                f"({base['passed']}/{base['of']}). Fix the change and rerun."
            )

    pr_lib.write_result(message=f"The evals record {len(scenarios)} scenario(s); new passes and is not worse than base.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
