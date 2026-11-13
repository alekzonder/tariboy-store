#!/usr/bin/env python3
"""Offline tests of scripts/workflow-eval.py and its fake GitHub.

They run no daemon and no model: the case schema of every Store workflow, the
criteria on recorded task states, the request history, the fixture values,
and the fake GitHub against a real fixture repository."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
STORE = HERE.parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("workflow_eval", HERE / "workflow-eval.py")
fake = load("fake_curl", HERE / "workflow_eval" / "fake_curl.py")
ACTOR = "agent:eval-000"


def snapshot(**fields):
    snap = {
        "status": "approval",
        "requests": [],
        "artifacts": {},
        "artifacts_before": {},
        "comments": [],
        "waits": [],
        "repo": {
            "branches": ["main"],
            "worktrees": 1,
            "main": "a" * 40,
            "head": "main",
            "head_checkouts": 0,
            "clean": True,
            "contains": {},
            "origin_branches": ["main"],
        },
    }
    snap.update(fields)
    return snap


def failed(results):
    return [name for name, passed, _ in results if not passed]


class SchemaTest(unittest.TestCase):
    def test_every_store_workflow_case_is_valid(self):
        for workflow_dir in sorted((STORE / "workflows").iterdir()):
            if not (workflow_dir / "Workflowfile.yaml").is_file():
                continue
            statuses = runner.workflow_statuses(workflow_dir)
            for case in runner.load_cases(workflow_dir):
                with self.subTest(workflow=workflow_dir.name, case=case.get("id")):
                    self.assertEqual(runner.validate_case(case, statuses, workflow_dir), [])

    def test_development_has_cases_for_every_pool_status(self):
        workflow_dir = STORE / "workflows" / "development"
        statuses = runner.workflow_statuses(workflow_dir)
        pool = {name for name, owner in statuses.items() if isinstance(owner, dict)}
        covered = {case["status"] for case in runner.load_cases(workflow_dir)}
        self.assertEqual(pool, {"plan", "implement", "complete"})
        self.assertLessEqual(pool, covered)

    def test_case_on_a_customer_status_is_refused(self):
        workflow_dir = STORE / "workflows" / "development"
        statuses = runner.workflow_statuses(workflow_dir)
        case = dict(runner.load_cases(workflow_dir)[0], status="approval")
        errors = runner.validate_case(case, statuses, workflow_dir)
        self.assertTrue(any("not owned by an agent pool" in error for error in errors))

    def test_unknown_criterion_and_step_are_refused(self):
        workflow_dir = STORE / "workflows" / "development"
        statuses = runner.workflow_statuses(workflow_dir)
        case = dict(runner.load_cases(workflow_dir)[0])
        case["criteria"] = {"vibes": True}
        case["path"] = [{"teleport": "plan"}]
        errors = " ".join(runner.validate_case(case, statuses, workflow_dir))
        self.assertIn("unknown criteria", errors)
        self.assertIn("path[0]", errors)


class SubstituteTest(unittest.TestCase):
    def test_fixture_values_replace_only_known_names(self):
        value = runner.substitute({"a": ["${repo}/x", "^\\d+$"]}, {"repo": "/r"})
        self.assertEqual(value, {"a": ["/r/x", "^\\d+$"]})

    def test_unknown_fixture_value_fails(self):
        with self.assertRaises(runner.EvalError):
            runner.substitute("${missing}", {})


class RequestsTest(unittest.TestCase):
    def test_history_from_visits_and_a_rejected_last_request(self):
        workflow = {
            "visits": [
                {"sequence": 1, "status": "backlog", "outcome": "start", "entered_by": "user:customer"},
                {"sequence": 2, "status": "plan", "outcome": "planned", "entered_by": "user:customer"},
                {"sequence": 3, "status": "approval", "entered_by": ACTOR},
            ],
            "last_request": {"outcome": "approved", "actor": "user:customer", "state": "rejected"},
        }
        requests = runner.requests_of(workflow)
        self.assertEqual(
            [(r["outcome"], r["actor"], r["state"]) for r in requests],
            [("start", "user:customer", "applied"), ("planned", ACTOR, "applied"), ("approved", "user:customer", "rejected")],
        )

    def test_artifacts_from_the_list_form(self):
        workflow = {"artifacts": [{"id": 1, "name": "plan", "value": "## Steps\n"}]}
        self.assertEqual(runner.artifacts_of(workflow), {"plan": "## Steps\n"})


class CriteriaTest(unittest.TestCase):
    PLAN = "## How it works\n\nx\n\n## Steps\n\nx\n\n## Verification\n\nx\n\n## Limitations\n\nx\n"

    def test_planned_with_four_headings_passes(self):
        criteria = {
            "outcome": {"name": "planned", "state": "applied"},
            "status": "approval",
            "artifacts": {"plan": {"headings": ["How it works", "Steps", "Verification", "Limitations"]}},
            "repo": {"branches": ["main"], "worktrees": 1, "clean": True, "main": "a" * 40},
        }
        snap = snapshot(
            requests=[{"outcome": "planned", "actor": ACTOR, "state": "applied"}],
            artifacts={"plan": self.PLAN},
        )
        self.assertEqual(failed(runner.check_criteria(criteria, snap, ACTOR)), [])

    def test_missing_heading_and_wrong_outcome_fail(self):
        criteria = {
            "outcome": {"name": "planned", "state": "applied"},
            "artifacts": {"plan": {"headings": ["Limitations"]}},
        }
        snap = snapshot(
            requests=[{"outcome": "planned", "actor": ACTOR, "state": "rejected"}],
            artifacts={"plan": "## Steps\n"},
        )
        self.assertEqual(failed(runner.check_criteria(criteria, snap, ACTOR)), ["outcome", "artifact plan"])

    def test_customer_requests_are_not_the_actor_outcome(self):
        criteria = {"outcome": {"name": "planned"}, "no_outcome": ["ready"]}
        snap = snapshot(requests=[{"outcome": "planned", "actor": "user:customer", "state": "applied"}])
        self.assertEqual(failed(runner.check_criteria(criteria, snap, ACTOR)), ["outcome"])

    def test_no_outcome_and_question(self):
        criteria = {"no_outcome": ["cleaned"], "question": True}
        asked = [{"requesting_principal": ACTOR, "expected_principal": "user:customer"}]
        ok = snapshot(waits=asked)
        bad = snapshot(requests=[{"outcome": "cleaned", "actor": ACTOR, "state": "applied"}])
        self.assertEqual(failed(runner.check_criteria(criteria, ok, ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, bad, ACTOR)), ["no_outcome", "question"])

    def test_unchanged_artifact_fails_changed(self):
        criteria = {"artifacts": {"plan": {"changed": True, "contains": ["--format"]}}}
        snap = snapshot(artifacts={"plan": "--json"}, artifacts_before={"plan": "--json"})
        result = runner.check_criteria(criteria, snap, ACTOR)
        self.assertEqual(failed(result), ["artifact plan"])
        self.assertIn("unchanged", result[0][2])

    def test_comment_labels_and_repo_state(self):
        labels = ["Required:", "Completed:", "Verification:", "Integration:", "Cleanup:"]
        criteria = {
            "comments": {"labels": labels},
            "repo": {"branches": ["main"], "worktrees": 1, "main_contains": "m" * 40},
        }
        good = snapshot(
            comments=[{"author": ACTOR, "body": "\n".join(f"{label} x" for label in labels)}],
            repo=dict(snapshot()["repo"], contains={"m" * 40: True}),
        )
        bad = snapshot(
            comments=[{"author": "user:customer", "body": "\n".join(labels)}],
            repo=dict(snapshot()["repo"], branches=["main", "feature"], worktrees=2, contains={"m" * 40: False}),
        )
        self.assertEqual(failed(runner.check_criteria(criteria, good, ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, bad, ACTOR)), ["comments", "repo"])

    def test_head_criterion_fails_on_a_detached_or_other_branch(self):
        criteria = {"repo": {"head": "main"}}
        on_main = snapshot()
        detached = snapshot(repo=dict(snapshot()["repo"], head=""))
        other = snapshot(repo=dict(snapshot()["repo"], head="dev/x"))
        self.assertEqual(failed(runner.check_criteria(criteria, on_main, ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, detached, ACTOR)), ["repo"])
        self.assertEqual(failed(runner.check_criteria(criteria, other, ACTOR)), ["repo"])

    def test_commands_criterion_reads_only_tool_commands(self):
        criteria = {"commands": {"absent": [r"\bsed -i\b", r"python3? -c"]}}
        prompt = '"text": "do not use sed -i or python3 -c"'

        def transcript(command):
            return prompt + '\n  "input": {\n    "command": ' + json.dumps(command) + ',\n    "description": "x"\n  }'

        clean = snapshot(transcript=transcript("git status && echo a > b.log"))
        inline = snapshot(transcript=transcript("sed -i 's/a/b/' evals.json"))
        self.assertEqual(failed(runner.check_criteria(criteria, clean, ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, inline, ACTOR)), ["commands"])

    def test_skills_first_criterion_needs_every_skill_before_the_first_other_tool(self):
        criteria = {"skills_first": ["tasks", "cli-text"]}

        def call(n, name, **tool_input):
            block = {"type": "tool_use", "tool_name": name, "tool_use_id": f"t{n}", "input": tool_input}
            return {"response": {"blocks": [block]}}

        def transcript(calls):
            # The request history repeats earlier calls; a repeat counts once.
            return "calls:\n" + json.dumps(calls + calls[:1])

        skill = lambda n, s: call(n, "Skill", skill=f"image-x:{s}")
        good = snapshot(transcript=transcript([skill(1, "tasks"), skill(2, "cli-text"), call(3, "Bash", command="ls")]))
        late = snapshot(transcript=transcript([skill(1, "tasks"), call(2, "Bash", command="ls"), skill(3, "cli-text")]))
        read_first = snapshot(transcript=transcript([call(1, "Read", file_path="/x"), skill(2, "tasks"), skill(3, "cli-text")]))
        self.assertEqual(failed(runner.check_criteria(criteria, good, ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, late, ACTOR)), ["skills_first"])
        self.assertEqual(failed(runner.check_criteria(criteria, read_first, ACTOR)), ["skills_first"])
        self.assertEqual(failed(runner.check_criteria(criteria, snapshot(), ACTOR)), ["skills_first"])

    def test_head_checkouts_criterion_fails_on_an_undone_switch(self):
        criteria = {"repo": {"head_checkouts": 0}}
        switched_back = snapshot(repo=dict(snapshot()["repo"], head="main", head_checkouts=2))
        self.assertEqual(failed(runner.check_criteria(criteria, snapshot(), ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, switched_back, ACTOR)), ["repo"])


    def test_main_updated_only_by_fails_on_a_forced_move(self):
        criteria = {"repo": {"main_updated_only_by": ["commit", "merge", "pull"]}}
        base = snapshot()["repo"]
        fast_forward = snapshot(repo=dict(base, main_reflog=["merge origin/main: Fast-forward", "commit (initial): Add widget list"]))
        forced = snapshot(repo=dict(base, main_reflog=["branch: Reset to origin/main", "commit (initial): Add widget list"]))
        reset = snapshot(repo=dict(base, main_reflog=["reset: moving to origin/main", "commit (initial): Add widget list"]))
        update_ref = snapshot(repo=dict(base, main_reflog=["", "commit (initial): Add widget list"]))
        self.assertEqual(failed(runner.check_criteria(criteria, snapshot(), ACTOR)), [])
        self.assertEqual(failed(runner.check_criteria(criteria, fast_forward, ACTOR)), [])
        for bad in (forced, reset, update_ref):
            self.assertEqual(failed(runner.check_criteria(criteria, bad, ACTOR)), ["repo"])


class OriginAndPullsTest(unittest.TestCase):
    def test_origin_branches_exact_count_and_contains(self):
        criteria = {
            "repo": {
                "origin_branches": ["main", "feature"],
                "origin_branch_count": 2,
                "origin_contains": [["feature", "p" * 40]],
            }
        }
        good = snapshot(repo=dict(snapshot()["repo"], origin_branches=["feature", "main"], origin_contains={"feature": {"p" * 40: True}}))
        extra = snapshot(repo=dict(snapshot()["repo"], origin_branches=["main", "feature", "feature-2"], origin_contains={"feature": {"p" * 40: False}}))
        self.assertEqual(failed(runner.check_criteria(criteria, good, ACTOR)), [])
        result = runner.check_criteria(criteria, extra, ACTOR)
        self.assertEqual(failed(result), ["repo"])
        self.assertIn("does not contain", result[0][2])
        self.assertIn("want 2", result[0][2])

    def test_pulls_count_heads_artifact_and_reviews(self):
        criteria = {"pulls": {"count": 1, "heads": ["feature"], "head_artifact": "branch", "reviews": 0}}
        good = snapshot(artifacts={"branch": "feature"}, pulls=[{"number": 1, "head": "feature", "reviews_posted": []}])
        bad = snapshot(
            artifacts={"branch": "feature"},
            pulls=[
                {"number": 1, "head": "feature", "reviews_posted": [{"id": 1}]},
                {"number": 2, "head": "feature-2", "reviews_posted": []},
            ],
        )
        self.assertEqual(failed(runner.check_criteria(criteria, good, ACTOR)), [])
        detail = runner.check_criteria(criteria, bad, ACTOR)[0][2]
        for text in ("2 pull requests", "heads", "differ from artifact branch", "1 reviews published"):
            self.assertIn(text, detail)

    def test_secrets_must_be_named_strings(self):
        workflow_dir = STORE / "workflows" / "pr-review"
        statuses = runner.workflow_statuses(workflow_dir)
        case = runner.load_cases(workflow_dir)[0]
        self.assertEqual(runner.validate_case(case, statuses, workflow_dir), [])
        for secrets in ({"GITHUB_TOKEN": "x"}, {"lower": "x"}, {"NAME": 1}, ["NAME"]):
            errors = runner.validate_case(dict(case, secrets=secrets), statuses, workflow_dir)
            self.assertTrue(any("secrets" in error for error in errors), secrets)


class WorktreeCommentTest(unittest.TestCase):
    def test_worktree_named_absolute_or_relative(self):
        repo = dict(snapshot()["repo"], linked_worktrees=[{"absolute": "/r/.worktrees/x", "relative": ".worktrees/x"}])
        criteria = {"comments": {"worktree_path": True}}
        for body in ("Worktree: `/r/.worktrees/x`", "worktree `.worktrees/x` of the main checkout"):
            snap = snapshot(repo=repo, comments=[{"author": ACTOR, "body": body}])
            self.assertEqual(failed(runner.check_criteria(criteria, snap, ACTOR)), [], body)
        snap = snapshot(repo=repo, comments=[{"author": ACTOR, "body": "PR opened"}])
        self.assertEqual(failed(runner.check_criteria(criteria, snap, ACTOR)), ["comments"])

    def test_no_linked_worktree_fails(self):
        snap = snapshot(comments=[{"author": ACTOR, "body": "x"}])
        self.assertEqual(failed(runner.check_criteria({"comments": {"worktree_path": True}}, snap, ACTOR)), ["comments"])


class GoalBlockTest(unittest.TestCase):
    def test_goal_block_needs_key_status_and_instructions(self):
        workflow_dir = STORE / "workflows" / "development"
        prompt = "## Goal\n\nkey: DEV-1\nstatus: plan\n\n# Plan\n\nProduce a plan\n"
        self.assertEqual(runner.goal_block_check(prompt, "DEV-1", "plan", workflow_dir), (True, "ok"))
        passed, detail = runner.goal_block_check(prompt, "DEV-1", "complete", workflow_dir)
        self.assertFalse(passed)
        self.assertIn("status complete", detail)


class FakeGitHubTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        env = dict(
            os.environ,
            EVAL_DIR=str(self.dir),
            EVAL_GITHUB_STATE=str(self.dir / "github.json"),
            EVAL_VARS=str(self.dir / "vars.json"),
        )
        script = STORE / "workflows" / "development" / "evals" / "fixtures" / "widget-repo.sh"
        subprocess.run(["bash", str(script), "pr-open"], env=env, check=True, capture_output=True)
        self.vars = json.loads((self.dir / "vars.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def test_pull_reports_the_pushed_head(self):
        status, pull = fake.handle(self.dir, "GET", "/repos/eval/widget/pulls/7", "", None)
        self.assertEqual(status, 200)
        self.assertEqual(pull["head"]["sha"], self.vars["head_sha"])
        self.assertEqual(pull["head"]["ref"], self.vars["branch"])
        self.assertEqual(pull["base"]["ref"], "main")

    def test_create_lists_and_refuses_a_duplicate(self):
        status, _ = fake.handle(self.dir, "POST", "/repos/eval/widget/pulls", "", json.dumps({"head": self.vars["branch"], "base": "main", "title": "t"}))
        self.assertEqual(status, 422)
        query = f"state=all&head=eval:{self.vars['branch']}&base=main&per_page=100&page=1"
        status, found = fake.handle(self.dir, "GET", "/repos/eval/widget/pulls", query, None)
        self.assertEqual((status, [p["number"] for p in found]), (200, [7]))
        status, _ = fake.handle(self.dir, "POST", "/repos/eval/widget/pulls", "", json.dumps({"head": "nope", "base": "main", "title": "t"}))
        self.assertEqual(status, 422)

    def test_files_list_the_diff_and_posted_reviews_are_kept(self):
        status, files = fake.handle(self.dir, "GET", "/repos/eval/widget/pulls/7/files", "", None)
        self.assertEqual(status, 200)
        self.assertEqual([(f["filename"], f["status"]) for f in files], [("widget.py", "modified")])
        self.assertTrue(files[0]["patch"].startswith("@@ "))
        self.assertIn("+import json", files[0]["patch"])
        status, _ = fake.handle(self.dir, "POST", "/repos/eval/widget/pulls/7/reviews", "", json.dumps({"body": "b", "event": "COMMENT"}))
        self.assertEqual(status, 200)
        pulls = runner.pulls_of(self.dir / "github.json")
        self.assertEqual([len(p["reviews_posted"]) for p in pulls], [1])

    def test_branch_pushed_keeps_the_partial_commit_only_on_origin(self):
        env = dict(
            os.environ,
            EVAL_DIR=str(self.dir / "pushed"),
            EVAL_GITHUB_STATE=str(self.dir / "pushed" / "github.json"),
            EVAL_VARS=str(self.dir / "pushed" / "vars.json"),
        )
        (self.dir / "pushed").mkdir()
        script = STORE / "workflows" / "development" / "evals" / "fixtures" / "widget-repo.sh"
        subprocess.run(["bash", str(script), "branch-pushed"], env=env, check=True, capture_output=True)
        values = json.loads((self.dir / "pushed" / "vars.json").read_text())
        repo = Path(values["repo"])
        state = runner.git_state(repo, [], [[values["branch"], values["partial_sha"]]], str(self.dir / "pushed" / "origin.git"))
        self.assertEqual(state["branches"], ["main"])
        self.assertEqual(state["worktrees"], 1)
        self.assertEqual(sorted(state["origin_branches"]), sorted(["main", values["branch"]]))
        self.assertEqual(state["origin_contains"], {values["branch"]: {values["partial_sha"]: True}})
        self.assertFalse(Path(values["other_worktree"]).exists())
        self.assertEqual(runner.pulls_of(self.dir / "pushed" / "github.json"), [])

    def test_curl_entry_point_writes_the_status_marker(self):
        shutil_copy = self.dir / "fake_curl.py"
        shutil_copy.write_bytes((HERE / "workflow_eval" / "fake_curl.py").read_bytes())
        shutil_copy.chmod(0o755)
        marker = "\n#tariboy-http-status:%{http_code}"
        result = subprocess.run(
            [str(shutil_copy), "--silent", "--fail-with-body", "--write-out", marker, "https://api.github.com/repos/eval/widget"],
            capture_output=True,
            text=True,
            check=False,
        )
        body, _, status = result.stdout.rpartition("\n#tariboy-http-status:")
        self.assertEqual((result.returncode, status), (0, "200"))
        self.assertEqual(json.loads(body)["default_branch"], "main")
        missing = subprocess.run(
            [str(shutil_copy), "--fail-with-body", "https://api.github.com/repos/eval/other"],
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing.returncode, 22)


if __name__ == "__main__":
    unittest.main()
