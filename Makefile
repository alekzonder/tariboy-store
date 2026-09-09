.PHONY: check

check:
	python3 -B skills/test_store_skills.py
	./scripts/test-check-images.sh
	./scripts/check-images.sh
	git diff --check
