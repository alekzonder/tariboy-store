.PHONY: check

check:
	python3 -B skills/test_store_skills.py
	python3 -B skills/cli-text/evals/check-text.py baseline >/dev/null
	python3 -B skills/cli-text/evals/check-text.py candidate >/dev/null
	python3 -B skills/cli-text/evals/check-consumers.py >/dev/null
	./scripts/test-check-images.sh
	./scripts/check-images.sh
	git diff --check
