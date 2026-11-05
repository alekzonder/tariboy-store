#!/usr/bin/env python3
"""Contracts for the image-improve workflow's check scripts: triage-check,
evals-check, pr-open and published-check."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import (  # noqa: E402
    BRANCH, HEAD_SHA, PR_URL, REJECT, SCRIPTS, FakeGitHub, ScriptCase, pull, task,
)

PLAN = """## How it works

The rule gains one sentence.

## Steps

1. Add the sentence.
2. Add an eval.

## Verification

`make check` and the eval.

## Limitations

None known.
"""
AUTONOMOUS = (
    "Decision: autonomous\nRoute: improve\nDuplicate: none\n"
    "Rule: tightens an existing rule, covered by a new eval, leaves ROLE.md and the skills alone\n"
    "Version: patch\n"
)
NEEDS_APPROVAL = "Decision: needs_approval\nRoute: improve\nDuplicate: none\nReason: adds a skill\n"
CLOSE = (
    "Decision: close\nRoute: improve\nDuplicate: IMPROVE-zz99\nClosed as: duplicate\n"
    "Reason: IMPROVE-zz99 asks for the same change and is open.\n"
)
VERIFICATION = f"`make check` on commit `{HEAD_SHA}`: exit 0."
DIGEST = "a" * 64


class TriageCheckTests(ScriptCase):
    script = SCRIPTS / "triage-check.py"

    def run_triage(self, outcome, artifacts):
        return self.run_script(self.script, task(artifacts=artifacts, outcome=outcome), outcome=outcome)

    def test_autonomous_accepted(self):
        code, result, _ = self.run_triage("autonomous", {"triage": AUTONOMOUS})
        self.assertEqual(code, 0, result)

    def test_outcome_comes_from_the_snapshot_without_the_environment(self):
        code, result, _ = self.run_script(self.script, task(artifacts={"triage": AUTONOMOUS}, outcome="autonomous"))
        self.assertEqual(code, 0, result)

    def test_missing_record_is_rejected(self):
        code, result, _ = self.run_triage("autonomous", {})
        self.rejected(code, result, "triage artifact is missing")

    def test_decision_must_equal_outcome(self):
        code, result, _ = self.run_triage("close", {"triage": AUTONOMOUS})
        self.rejected(code, result, "'autonomous'", "outcome close")

    def test_other_route_cannot_continue(self):
        record = AUTONOMOUS.replace("Route: improve", "Route: tariboyd")
        code, result, _ = self.run_triage("autonomous", {"triage": record})
        self.rejected(code, result, "wrong_route")

    def test_duplicate_cannot_continue(self):
        record = AUTONOMOUS.replace("Duplicate: none", "Duplicate: IMPROVE-zz99")
        code, result, _ = self.run_triage("autonomous", {"triage": record})
        self.rejected(code, result, "Duplicate")

    def test_autonomous_without_rule_is_rejected(self):
        record = AUTONOMOUS.replace("Rule: tightens an existing rule, covered by a new eval, leaves ROLE.md and the skills alone\n", "")
        code, result, _ = self.run_triage("autonomous", {"triage": record})
        self.rejected(code, result, "Rule line")

    def test_autonomous_with_a_minor_version_is_outside_the_rule(self):
        record = AUTONOMOUS.replace("Version: patch", "Version: minor")
        code, result, _ = self.run_triage("autonomous", {"triage": record})
        self.rejected(code, result, "needs_approval")

    def test_needs_approval_accepted_with_plan(self):
        code, result, _ = self.run_triage("needs_approval", {"triage": NEEDS_APPROVAL, "plan": PLAN})
        self.assertEqual(code, 0, result)

    def test_needs_approval_without_plan_is_rejected(self):
        code, result, _ = self.run_triage("needs_approval", {"triage": NEEDS_APPROVAL})
        self.rejected(code, result, "plan artifact is missing")

    def test_needs_approval_with_an_incomplete_plan_is_rejected(self):
        code, result, _ = self.run_triage("needs_approval", {"triage": NEEDS_APPROVAL, "plan": "## Steps\n\n1. Do it.\n"})
        self.rejected(code, result, "'How it works' is missing", "'Limitations' is missing")

    def test_close_accepted_for_a_duplicate(self):
        code, result, _ = self.run_triage("close", {"triage": CLOSE})
        self.assertEqual(code, 0, result)

    def test_close_accepted_as_noise_without_a_duplicate(self):
        record = "Decision: close\nRoute: other\nDuplicate: none\nClosed as: noise\nReason: The finding has no evidence of a problem.\n"
        code, result, _ = self.run_triage("close", {"triage": record})
        self.assertEqual(code, 0, result)

    def test_close_duplicate_needs_the_other_key(self):
        record = CLOSE.replace("Duplicate: IMPROVE-zz99", "Duplicate: none")
        code, result, _ = self.run_triage("close", {"triage": record})
        self.rejected(code, result, "key of the task it repeats")

    def test_close_needs_a_known_reason_kind_and_text(self):
        code, result, _ = self.run_triage("close", {"triage": CLOSE.replace("duplicate\nReason", "other\nReason")})
        self.rejected(code, result, "Closed as")
        code, result, _ = self.run_triage("close", {"triage": CLOSE.replace("IMPROVE-zz99 asks for the same change and is open.", "dup")})
        self.rejected(code, result, "Reason")

    def test_unknown_outcome_is_a_failure(self):
        code, result, _ = self.run_triage("approved", {"triage": AUTONOMOUS})
        self.assertEqual(code, 1)


class EvalsCheckTests(ScriptCase):
    script = SCRIPTS / "evals-check.py"

    @staticmethod
    def evals(**changes):
        data = {
            "model": "claude-sonnet-5-5",
            "cost_usd": 1.5,
            "scenarios": [
                {"id": "wait-object", "base": {"passed": 0, "of": 3}, "new": {"passed": 3, "of": 3}},
                {"id": "text-read", "base": {"passed": 1, "of": 3}, "new": {"passed": 2, "of": 3}},
            ],
        }
        data.update(changes)
        return {key: value for key, value in data.items() if value is not None}

    def run_evals(self, value):
        artifacts = {} if value is None else {"evals": value if isinstance(value, str) else json.dumps(value)}
        return self.run_script(self.script, task(status="implement", outcome="ready", artifacts=artifacts))

    def test_accepted(self):
        code, result, _ = self.run_evals(self.evals())
        self.assertEqual(code, 0, result)

    def test_missing_artifact_is_rejected(self):
        code, result, _ = self.run_evals(None)
        self.rejected(code, result, "evals artifact is missing")

    def test_not_json_is_rejected(self):
        code, result, _ = self.run_evals("it passed")
        self.rejected(code, result, "not valid JSON")

    def test_a_scenario_without_base_is_rejected(self):
        scenarios = [{"id": "a", "new": {"passed": 3, "of": 3}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "no base result")

    def test_a_scenario_without_new_is_rejected(self):
        scenarios = [{"id": "a", "base": {"passed": 0, "of": 3}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "no new result")

    def test_new_below_two_of_three_is_rejected(self):
        scenarios = [{"id": "a", "base": {"passed": 0, "of": 3}, "new": {"passed": 1, "of": 3}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "Scenario 'a'", "at least 2 of 3")

    def test_new_worse_than_base_is_rejected(self):
        scenarios = [{"id": "a", "base": {"passed": 3, "of": 3}, "new": {"passed": 2, "of": 3}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "worse than base")

    def test_fewer_than_three_runs_is_rejected(self):
        scenarios = [{"id": "a", "base": {"passed": 0, "of": 1}, "new": {"passed": 1, "of": 1}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "at least 3 are needed")

    def test_more_runs_keep_the_ratio(self):
        scenarios = [{"id": "a", "base": {"passed": 1, "of": 5}, "new": {"passed": 4, "of": 5}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.assertEqual(code, 0, result)
        scenarios = [{"id": "a", "base": {"passed": 0, "of": 5}, "new": {"passed": 3, "of": 5}}]
        code, result, _ = self.run_evals(self.evals(scenarios=scenarios))
        self.rejected(code, result, "at least 2 of 3")

    def test_model_and_cost_are_required(self):
        code, result, _ = self.run_evals(self.evals(model=None))
        self.rejected(code, result, "'model'")
        code, result, _ = self.run_evals(self.evals(cost_usd=None))
        self.rejected(code, result, "'cost_usd'")

    def test_not_applicable_needs_a_reason(self):
        data = self.evals(scenarios=None, not_applicable="Only a typo in a comment changed.")
        code, result, _ = self.run_evals(data)
        self.assertEqual(code, 0, result)
        code, result, _ = self.run_evals(self.evals(scenarios=None, not_applicable="none"))
        self.rejected(code, result, "no 'scenarios'")
        code, result, _ = self.run_evals(self.evals(scenarios=None))
        self.rejected(code, result, "no 'scenarios'")

    def test_duplicate_scenario_ids_are_rejected(self):
        one = {"id": "a", "base": {"passed": 0, "of": 3}, "new": {"passed": 3, "of": 3}}
        code, result, _ = self.run_evals(self.evals(scenarios=[one, one]))
        self.rejected(code, result, "appears twice")


class PublishedCheckTests(ScriptCase):
    script = SCRIPTS / "published-check.py"

    @staticmethod
    def publication(**changes):
        data = {
            "images": [
                {"name": "tariboy-image-creator", "version": "0.21.0", "version_digest": DIGEST, "latest_digest": DIGEST}
            ],
            "workflows": [{"name": "image-improve", "workflow_version": "0.1.0"}],
        }
        data.update(changes)
        return data

    def run_publication(self, value):
        artifacts = {} if value is None else {"publication": value if isinstance(value, str) else json.dumps(value)}
        return self.run_script(self.script, task(status="publish", outcome="published", artifacts=artifacts))

    def test_accepted(self):
        code, result, _ = self.run_publication(self.publication())
        self.assertEqual(code, 0, result)

    def test_workflow_only_accepted(self):
        code, result, _ = self.run_publication(self.publication(images=[]))
        self.assertEqual(code, 0, result)

    def test_missing_artifact_is_rejected(self):
        code, result, _ = self.run_publication(None)
        self.rejected(code, result, "publication artifact is missing")

    def test_different_digests_are_rejected(self):
        image = {"name": "reviewer", "version": "0.3.1", "version_digest": DIGEST, "latest_digest": "b" * 64}
        code, result, _ = self.run_publication(self.publication(images=[image]))
        self.rejected(code, result, "different digests")

    def test_missing_latest_is_rejected(self):
        image = {"name": "reviewer", "version": "0.3.1", "version_digest": DIGEST}
        code, result, _ = self.run_publication(self.publication(images=[image]))
        self.rejected(code, result, "latest_digest")

    def test_missing_version_is_rejected(self):
        image = {"name": "reviewer", "version_digest": DIGEST, "latest_digest": DIGEST}
        code, result, _ = self.run_publication(self.publication(images=[image]))
        self.rejected(code, result, "'version'")

    def test_short_digest_is_rejected(self):
        image = {"name": "reviewer", "version": "0.3.1", "version_digest": DIGEST[:12], "latest_digest": DIGEST[:12]}
        code, result, _ = self.run_publication(self.publication(images=[image]))
        self.rejected(code, result, "full 64-character")

    def test_empty_publication_is_rejected(self):
        code, result, _ = self.run_publication(self.publication(images=[], workflows=[]))
        self.rejected(code, result, "lists no image")

    def test_workflow_needs_its_version(self):
        code, result, _ = self.run_publication(self.publication(workflows=[{"name": "image-improve"}]))
        self.rejected(code, result, "workflow_version")

    def test_unknown_keys_and_duplicates_are_rejected(self):
        code, result, _ = self.run_publication(self.publication(extra=1))
        self.rejected(code, result, "unknown keys")
        image = self.publication()["images"][0]
        code, result, _ = self.run_publication(self.publication(images=[image, image]))
        self.rejected(code, result, "appears twice")


class PullRequestOpenTests(ScriptCase):
    script = SCRIPTS / "pr-open.py"

    def setUp(self):
        super().setUp()
        self.github = FakeGitHub().__enter__()
        self.addCleanup(self.github.__exit__)
        self.github.routes["/repos/acme/widget"] = (200, {"default_branch": "main"})
        self.github.routes["/repos/acme/widget/pulls/42"] = (200, pull())

    def run_open(self, **artifacts):
        merged = {"pull_request": PR_URL, "branch": BRANCH, "verification": VERIFICATION, **artifacts}
        merged = {name: value for name, value in merged.items() if value is not None}
        return self.run_script(
            self.script, task(status="deliver", outcome="submitted", artifacts=merged),
            env={"GITHUB_API_URL": self.github.url},
        )

    def test_accepted(self):
        code, result, _ = self.run_open()
        self.assertEqual(code, 0, result)

    def test_head_not_verified_is_rejected(self):
        code, result, _ = self.run_open(verification="`make check` on commit " + "f" * 40)
        self.rejected(code, result, "does not name the head commit")

    def test_other_branch_is_rejected(self):
        code, result, _ = self.run_open(branch="task/other")
        self.rejected(code, result, "head branch")

    def test_closed_pull_request_is_rejected(self):
        self.github.routes["/repos/acme/widget/pulls/42"] = (200, pull(state="closed", closed_at="2026-11-05T11:00:00Z"))
        code, result, _ = self.run_open()
        self.rejected(code, result, "closed without a merge")

    def test_task_key_in_the_title_is_rejected(self):
        self.github.routes["/repos/acme/widget/pulls/42"] = (200, pull(title="Fix IMPROVE-ab12"))
        code, result, _ = self.run_open()
        self.rejected(code, result, "names the task key")

    def test_missing_pull_request_is_rejected(self):
        code, result, _ = self.run_open(pull_request=None)
        self.rejected(code, result, "pull_request artifact is missing")

    def test_manifest_scripts_exist(self):
        self.assertTrue((SCRIPTS / "pr-watch.py").is_file())


if __name__ == "__main__":
    unittest.main()
