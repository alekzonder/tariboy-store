#!/usr/bin/env python3
"""Checks of the review cycle selection: `review.py candidates` and `coverage` on fixed rows."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "review.py"
NOW = "2026-11-03T12:00:00Z"


def it(agent, n, hour, version="1.0.0", **kw):
    """One finished iteration that ended on 2026-11-03 (hour may be negative: the day before)."""
    day, h = ("03", hour) if hour >= 0 else ("02", 24 + hour)
    row = {"agent": agent, "id": f"{agent}-{n}", "status": "done", "productive": True,
           "ended_at": f"2026-11-{day}T{h:02d}:30:00.123456789Z", "image_version": version, "assessed": False}
    row.update(kw)
    return row


def run(cmd, rows, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "rows.json"
        src.write_text(json.dumps(rows))
        args = [sys.executable, "-B", str(SCRIPT), cmd, "--input", str(src), "--now", NOW, *extra]
        if cmd == "candidates":
            args += ["--dir", tmp]
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr)
        summary = json.loads(proc.stdout)
        picked = json.loads((Path(tmp) / "candidates.json").read_text()) if cmd == "candidates" else None
        return summary, picked


class Selection(unittest.TestCase):
    def test_problem_iterations_come_first_newest_first(self):
        rows = [it("a", 1, 1), it("a", 2, 2, status="harness_error"), it("a", 3, 3, status="timeout"),
                it("b", 1, 4, marks=["question"]), it("b", 2, 5, marks=["check_rejected"]), it("b", 3, 6)]
        _, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked[:4]], ["b-2", "b-1", "a-3", "a-2"])
        self.assertTrue(all(r["reason"] == "problem" for r in picked[:4]))
        self.assertEqual([r["id"] for r in picked[4:]], ["b-3", "a-1"])

    def test_idle_iterations_are_not_taken(self):
        rows = [it("a", n, n) for n in range(1, 5)] + [it("a", 9, 9, productive=False)]
        summary, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked], ["a-4", "a-3", "a-2", "a-1"])
        self.assertTrue(all(r["reason"] == "pair_sample" for r in picked))
        self.assertEqual(summary["skipped"]["idle"], 1)

    def test_no_pair_quota_every_iteration_of_a_pair_is_taken(self):
        rows = [it("a", n, n, status="harness_error") for n in range(1, 6)] + [it("a", 8, 8), it("a", 9, 9)]
        rows += [it("b", 1, 1, marks=["question"]), it("b", 2, 2), it("b", 3, 3), it("b", 4, 4)]
        summary, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked],
                         ["a-5", "a-4", "a-3", "a-2", "b-1", "a-1", "a-9", "b-4", "a-8", "b-3", "b-2"])
        self.assertEqual(summary["candidates"], 11)
        self.assertEqual(summary["skipped"]["over_sample"], 0)

    def test_sample_size_cuts_after_problems_and_an_even_round_over_pairs(self):
        rows = [it("a", n, n % 12, status="harness_error") for n in range(1, 6)]       # 5 problems of a 1.0.0
        rows += [it("a", 100 + n, n % 12) for n in range(1, 41)]                       # 40 of a 1.0.0
        rows += [it("a", 200 + n, n % 12, version="1.1.0") for n in range(1, 21)]      # 20 of a 1.1.0
        rows += [it("b", n, n % 12, marks=["question"] if n == 1 else []) for n in range(1, 31)]  # 30 of b
        summary, picked = run("candidates", rows)
        self.assertEqual(summary["sample_size"], 50)
        self.assertEqual(summary["candidates"], 50)
        self.assertEqual(summary["problem"], 6)
        self.assertEqual(summary["skipped"]["over_sample"], 95 - 50)
        self.assertTrue(all(r["reason"] == "problem" for r in picked[:6]))
        self.assertTrue(all(r["reason"] == "pair_sample" for r in picked[6:]))
        per_pair = {}
        for r in picked[6:]:
            key = (r["agent"], r["image_version"])
            per_pair[key] = per_pair.get(key, 0) + 1
        self.assertEqual(len(per_pair), 3)
        self.assertLessEqual(max(per_pair.values()) - min(per_pair.values()), 1)

    def test_sample_size_is_a_parameter(self):
        rows = [it("a", n, n) for n in range(1, 11)]
        summary, picked = run("candidates", rows, "--size", "4")
        self.assertEqual([r["id"] for r in picked], ["a-10", "a-9", "a-8", "a-7"])
        self.assertEqual(summary["skipped"]["over_sample"], 6)

    def test_even_sample_per_agent_and_version_newest_first(self):
        rows = [it("a", n, n) for n in range(1, 11)]                     # 10 iterations of a 1.0.0
        rows += [it("a", 20 + n, n, version="1.1.0") for n in range(1, 3)]  # 2 of a 1.1.0
        rows += [it("b", n, n) for n in range(1, 6)]                     # 5 of b
        summary, picked = run("candidates", rows)
        ids = [r["id"] for r in picked]
        self.assertEqual(summary["active_pairs"], 3)
        self.assertEqual(len(ids), 17)
        # Round robin: the first three picks cover three different pairs.
        self.assertEqual(len({(r["agent"], r["image_version"]) for r in picked[:3]}), 3)
        # Newest first inside a pair.
        self.assertEqual([i for i in ids if i.startswith("a-") and int(i[2:]) < 20][:3], ["a-10", "a-9", "a-8"])

    def test_assessed_iterations_are_not_repeated(self):
        rows = [it("a", 1, 1, assessed=True), it("a", 2, 2, assessed=True), it("a", 3, 3), it("a", 4, 4)]
        summary, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked], ["a-4", "a-3"])
        self.assertEqual(summary["skipped"]["assessed"], 2)

    def test_window_is_the_last_24_hours(self):
        rows = [it("a", 1, -13), it("a", 2, -11, status="harness_error"), it("a", 3, 11),
                {"agent": "a", "id": "a-run", "status": "running", "started_at": "2026-11-03T11:00:00Z"}]
        summary, picked = run("candidates", rows)
        # a-1 ended 2026-11-02T11:30, more than 24 hours before 12:00 on the 3rd.
        self.assertEqual([r["id"] for r in picked], ["a-2", "a-3"])
        self.assertEqual(summary["skipped"]["older_than_window"], 1)
        self.assertEqual(summary["skipped"]["running"], 1)

    def test_old_unselected_iterations_are_never_candidates_again(self):
        rows = [it("a", n, -13 - n % 5) for n in range(5)] + [it("a", 9, 10)]
        summary, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked], ["a-9"])
        self.assertEqual(summary["skipped"]["older_than_window"], 5)


class Coverage(unittest.TestCase):
    def test_metric_one(self):
        rows = [it("a", n, n, assessed=n <= 3) for n in range(1, 8)]        # 3 of 7
        rows += [it("b", 1, 1, assessed=True), it("b", 2, 2, assessed=True)]  # 2 of 2
        rows += [it("c", n, n, assessed=False) for n in range(1, 5)]        # 0 of 4
        rows += [it("c", 9, 9, productive=False)]                           # idle: not counted
        rows += [it("d", 1, -20, assessed=False)]                           # outside the window
        summary, _ = run("coverage", rows)
        self.assertEqual(summary["iterations"], 13)
        self.assertEqual(summary["assessed_iterations"], 5)
        self.assertEqual(summary["active_pairs"], 3)
        self.assertEqual(summary["pairs_with_assessment"], 2)


if __name__ == "__main__":
    unittest.main()
