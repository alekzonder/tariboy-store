#!/usr/bin/env python3
"""Tests for scripts/check-skills-lock.py on a temporary Store."""
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("check_skills_lock", os.path.join(HERE, "check-skills-lock.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class CheckSkillsLock(unittest.TestCase):
    def store(self, tmp, digest=None):
        write(os.path.join(tmp, "skills", "demo", "SKILL.md"), "---\nname: demo\n---\n")
        write(os.path.join(tmp, "skills", "demo", "scripts", "run.sh"), "echo hi\n")
        write(os.path.join(tmp, "skills", "demo", "Notes.md"), "notes\n")
        actual = module.skill_hash(os.path.join(tmp, "skills", "demo"))
        lock = {
            "version": 1,
            "skills": {
                "demo": {"source": "../../skills/demo", "sourceType": "local", "computedHash": digest or actual},
                "remote": {"source": "o/r", "sourceType": "github", "computedHash": "0" * 64},
            },
        }
        write(os.path.join(tmp, "images", "img", "skills-lock.json"), json.dumps(lock))

    def test_matching_lock_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.store(tmp)
            self.assertEqual(module.check(tmp), [])

    def test_stale_hash_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.store(tmp, digest="f" * 64)
            errors = module.check(tmp)
            self.assertEqual(len(errors), 1)
            self.assertIn("skill demo", errors[0])

    def test_changed_skill_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.store(tmp)
            write(os.path.join(tmp, "skills", "demo", "scripts", "run.sh"), "echo changed\n")
            self.assertEqual(len(module.check(tmp)), 1)

    def test_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.store(tmp)
            os.rename(os.path.join(tmp, "skills", "demo"), os.path.join(tmp, "skills", "gone"))
            self.assertIn("is missing", module.check(tmp)[0])


if __name__ == "__main__":
    unittest.main()
