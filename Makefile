.PHONY: check

check:
	python3 -B skills/test_store_skills.py
	python3 -B skills/cli-text/evals/check-text.py baseline >/dev/null
	python3 -B skills/cli-text/evals/check-text.py candidate >/dev/null
	python3 -B skills/cli-text/evals/check-consumers.py >/dev/null
	python3 -B scripts/test-closure-monitor.py
	./scripts/test-check-images.sh
	python3 -B workflows/development/tests/test_checks.py
	python3 -B workflows/development/tests/test_monitor.py
	python3 -B images/tariboy-workflow-developer/skills/github-pr-workflow/tests/test_github_pr.py
	python3 -B workflows/pr-review/tests/test_scripts.py
	python3 -B images/reviewer/skills/pull-request-review/tests/test_github_review.py
	./scripts/check-images.sh
	git diff --check
