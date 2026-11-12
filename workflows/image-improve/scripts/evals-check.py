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
least 2 of 3 (the same ratio for more runs) and is better than the base: a
scenario that passes as often on the base as on the change does not show that
the change works. A scenario that only guards a behavior that already works
may carry "guard": "reason" (plain text of at least 20 characters) and then
may equal the base; the agent asks the customer before it sets a guard, and
the customer reads the reason in the pull request. A change with no new or changed scenario, for example one that only fixes a
typo, says so with {"not_applicable": "reason"} instead of "scenarios"; the
reason is plain text of at least 20 characters. The model and the cost are
required in both forms; the model is one pinned MODEL ID, never an alias such as haiku, so the run can be repeated and its price is known.

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
MODEL_ALIASES = {"haiku", "sonnet", "opus", "fable", "default", "latest", "best", "small", "fast"}
MIN_REASON = 20


def reject(message: str) -> int:
    pr_lib.write_result(message=message)
    return pr_lib.REJECT_EXIT


def alias_problem(model: str) -> str | None:
    """A pinned MODEL ID names one model version and has a digit, as claude-haiku-5-5."""
    name = model.strip().lower()
    if name in MODEL_ALIASES or name.endswith("-latest") or not any(c.isdigit() for c in name):
        return (
            f"The model '{model.strip()}' is an alias. Pin one MODEL ID with its version, "
            "for example claude-haiku-5-5, run the base and the change again on it, and "
            "record it in 'model'."
        )
    return None


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
        return reject("The evals artifact has no 'model': name the pinned MODEL ID of the runs.")
    problem = alias_problem(model)
    if problem:
        return reject(problem)
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
        guard = scenario.get("guard")
        if guard is not None and (not isinstance(guard, str) or len(guard.strip()) < MIN_REASON):
            return reject(
                f"Scenario '{name}': 'guard' must be the reason, plain text of at least "
                f"{MIN_REASON} characters, that the scenario only guards a behavior that already works."
            )
        if new["passed"] * base["of"] == base["passed"] * new["of"] and guard is None:
            return reject(
                f"Scenario '{name}': new ({new['passed']}/{new['of']}) equals base "
                f"({base['passed']}/{base['of']}), so the scenario does not separate the old "
                "text from the new text. Do not advance and do not publish. Change the text "
                "so that the scenario fails on the base and passes on the change, then rerun "
                "both; never edit the scenario's criteria. If the scenario only guards a "
                "behavior that already works, ask the customer with ttasks ask, and set "
                "'guard' to the reason only after the customer answers."
            )

    pr_lib.write_result(message=f"The evals record {len(scenarios)} scenario(s); new passes and is better than base or is a recorded guard.")
    return 0


if __name__ == "__main__":
    pr_lib.run(main)
