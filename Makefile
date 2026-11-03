.PHONY: check workflow-eval

# The workflow whose cases `make workflow-eval` runs, and extra runner flags,
# for example ARGS='--case plan-new-task --repeat 3 --model sonnet'.
WORKFLOW ?= development
ARGS ?=

check:
	python3 -B skills/test_store_skills.py
	python3 -B skills/cli-text/evals/check-text.py baseline >/dev/null
	python3 -B skills/cli-text/evals/check-text.py candidate >/dev/null
	python3 -B skills/cli-text/evals/check-consumers.py >/dev/null
	python3 -B skills/cli-text/evals/check-shell-layer.py >/dev/null
	python3 -B scripts/check-writing-style.py
	python3 -B scripts/test-check-evals.py
	python3 -B scripts/check-evals.py
	python3 -B scripts/test-closure-monitor.py
	./scripts/test-check-images.sh
	python3 -B workflows/development/tests/test_checks.py
	python3 -B workflows/development/tests/test_monitor.py
	python3 -B images/tariboy-workflow-developer/skills/github-pr-workflow/tests/test_github_pr.py
	python3 -B workflows/pr-review/tests/test_scripts.py
	python3 -B images/reviewer/skills/pull-request-review/tests/test_github_review.py
	python3 -B images/tariboy-image-creator/skills/iteration-review/tests/test_review.py
	./scripts/check-images.sh
	python3 -B scripts/test-workflow-eval.py
	for dir in workflows/*/; do python3 -B scripts/workflow-eval.py --workflow "$$(basename "$$dir")" --render-only || exit 1; done
	git diff --check

# Runs every eval case of WORKFLOW with a model in an isolated daemon. It
# spends AI budget, so it is not part of `check`.
workflow-eval:
	python3 -B scripts/workflow-eval.py --workflow $(WORKFLOW) $(ARGS)
