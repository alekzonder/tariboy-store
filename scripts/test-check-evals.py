#!/usr/bin/env python3
"""Tests for scripts/check-evals.py on temporary Git repositories."""
import importlib.util
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "check-evals.py"
spec = importlib.util.spec_from_file_location("check_evals", SCRIPT)
check_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_evals)


class CheckEvalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        subprocess.run(["git", "-C", str(self.root), "add", path], check=True)

    def suite(self, root, cases):
        self.write(f"{root}/evals/evals.json", json.dumps({"skill_name": "x", "evals": cases}))

    def run_check(self, known=None):
        if known is not None:
            self.write("scripts/check-evals-known.txt", known)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_evals.main(["--root", str(self.root)])
        return code, out.getvalue(), err.getvalue()

    def test_clean_suites_pass(self):
        self.suite("skills/a", [{"id": "one", "files": ["evals/files/in.json"]}])
        self.write("skills/a/evals/files/in.json", "{}")
        self.write("skills/a/evals/README.md", "# notes")
        self.write("skills/a/evals/check-text.py", "print(1)")
        self.suite("workflows/w", [{"id": "two", "fixture": {"script": "evals/fixtures/repo.sh"}}])
        self.write("workflows/w/evals/fixtures/repo.sh", 'cp "$(dirname "$0")/../files/seed.txt" "$EVAL_DIR"\n. ./lib.sh\n')
        self.write("workflows/w/evals/fixtures/lib.sh", "true")
        self.write("workflows/w/evals/files/seed.txt", "seed")
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertIn("2 suites checked, 0 known violations", out)

    def test_unused_file_fails(self):
        self.suite("skills/a", [{"id": "one"}])
        self.write("skills/a/evals/files/old.json", "{}")
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("unused: skills/a/evals/files/old.json", err)

    def test_missing_reference_fails(self):
        self.suite("skills/a", [{"id": "one", "files": ["evals/files/gone.json"]}])
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("missing: skills/a/evals/evals.json case one -> evals/files/gone.json", err)

    def test_untracked_file_is_ignored(self):
        self.suite("skills/a", [{"id": "one"}])
        stray = self.root / "skills/a/evals/files/local-results.json"
        stray.parent.mkdir(parents=True)
        stray.write_text("{}")
        code, _, err = self.run_check()
        self.assertEqual(code, 0, err)

    def test_duplicate_between_suites_fails(self):
        self.suite("skills/a", [{"id": "one", "files": ["evals/files/pack.md"]}])
        self.suite("images/b", [{"id": "two", "files": ["evals/files/review/pack.md"]}])
        self.write("skills/a/evals/files/pack.md", "same")
        self.write("images/b/evals/files/review/pack.md", "same")
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("duplicate: skills/a/evals/files/pack.md (same content as images/b/evals/files/review/pack.md)", err)
        self.assertIn("duplicate: images/b/evals/files/review/pack.md", err)

    def test_nested_skill_suite_is_its_own_suite(self):
        self.suite("images/b", [{"id": "img"}])
        self.suite("images/b/skills/s", [{"id": "skill", "files": ["evals/files/pack.md"]}])
        self.write("images/b/skills/s/evals/files/pack.md", "pack")
        code, _, err = self.run_check()
        self.assertEqual(code, 0, err)

    def test_reference_into_another_suite_counts(self):
        self.suite("images/b/skills/s", [{"id": "skill", "files": ["evals/files/pack.md"]}])
        self.suite("images/b", [{"id": "img", "files": ["skills/s/evals/files/pack.md"]}])
        self.suite("skills/c", [{"id": "other", "files": ["../../images/b/skills/s/evals/files/extra.md"]}])
        self.write("images/b/skills/s/evals/files/pack.md", "pack")
        self.write("images/b/skills/s/evals/files/extra.md", "extra")
        code, _, err = self.run_check()
        self.assertEqual(code, 0, err)

    def test_run_results_fail(self):
        self.suite("skills/a", [{"id": "one"}])
        for name in ("results.json", "case-baseline.md", "run-candidate.md", "grading.json",
                     "run.log", "provenance.json", "baseline.json", "transcript.txt"):
            self.write(f"skills/a/evals/{name}", name)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        for name in ("results.json", "case-baseline.md", "run-candidate.md", "grading.json",
                     "run.log", "provenance.json", "baseline.json", "transcript.txt"):
            self.assertIn(f"run-result: skills/a/evals/{name}", err)

    def test_known_violation_passes_and_stale_line_fails(self):
        self.suite("skills/a", [{"id": "one"}])
        self.write("skills/a/evals/results.md", "old run")
        code, out, err = self.run_check("# known\nrun-result: skills/a/evals/results.md\n")
        self.assertEqual(code, 0, err)
        self.assertIn("1 known violations", out)
        subprocess.run(["git", "-C", str(self.root), "rm", "-q", "-f", "skills/a/evals/results.md"], check=True)
        code, _, err = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("fixed, remove the line: run-result: skills/a/evals/results.md", err)

    def test_store_passes(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = check_evals.main([])
        self.assertEqual(code, 0, err.getvalue())


if __name__ == "__main__":
    unittest.main()
