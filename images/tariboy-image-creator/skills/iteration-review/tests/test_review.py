#!/usr/bin/env python3
"""Checks of the review cycle selection: `review.py candidates` and `coverage` on fixed rows."""
import json
import shutil
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


FAKE_TARIBOY = r'''#!/usr/bin/env python3
"""A fake `tariboy assessment add|ls` that keeps the written assessments in $FAKE_DB."""
import json, os, sys
db_path = os.environ["FAKE_DB"]
db = json.load(open(db_path)) if os.path.exists(db_path) else []
args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else ""
if args[:2] == ["assessment", "add"]:
    obj = json.load(open(opt("--file")))
    if obj.get("iteration_id") and obj.get("task_key"):
        sys.exit("task_key is not linked to the iteration")
    row = dict(obj, id=f"as-{len(db) + 1}", assessor_agent=os.environ["TARIBOY_AGENT"])
    db.append(row)
    json.dump(db, open(db_path, "w"))
    print(json.dumps({"assessment": row}))
elif args[:2] == ["assessment", "ls"]:
    rows = [r for r in db if (not opt("--assessor") or r["assessor_agent"] == opt("--assessor"))
            and (not opt("--iteration") or r.get("iteration_id") == opt("--iteration"))
            and (not opt("--task") or r.get("task_key") == opt("--task"))]
    print(json.dumps({"assessments": rows}))
else:
    sys.exit(f"unexpected: {args}")
'''


def assessment(iteration="", task=""):
    obj = {"rubric_version": "iteration-review/1", "summary": "ok",
           "axes": [{"axis": a, "verdict": "scored", "score": 80} for a in ("image_process", "role", "task_fit")]}
    if iteration:
        obj["iteration_id"] = iteration
    if task:
        obj["task_key"] = task
    return obj


class Add(unittest.TestCase):
    """`review.py add` writes each assessment once, also when files of an earlier call stay in out/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "bin").mkdir()
        fake = root / "bin" / "tariboy"
        fake.write_text(FAKE_TARIBOY.replace("/usr/bin/env python3", sys.executable, 1))
        fake.chmod(0o755)
        self.dir = root / "cycle"
        (self.dir / "out").mkdir(parents=True)
        self.db = root / "db.json"
        self.env = {"PATH": f"{root / 'bin'}:/usr/bin:/bin", "FAKE_DB": str(self.db), "TARIBOY_AGENT": "reviewer-1"}

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, obj):
        (self.dir / "out" / name).write_text(json.dumps(obj))

    def add(self, cycle_dir=None):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "add", "--dir", str(cycle_dir or self.dir)],
                              capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return json.loads(proc.stdout)

    def written(self):
        return json.loads(self.db.read_text()) if self.db.exists() else []

    def test_repeated_add_after_a_dropped_task_key_writes_nothing_again(self):
        self.put("it-1.json", assessment("it-1", "DEV-1"))   # the daemon refuses the link: written without task_key
        self.put("it-2.json", assessment("it-2"))
        first = self.add()
        self.assertEqual(len(first["written"]), 2)
        self.assertEqual(len(self.written()), 2)
        second = self.add()
        self.assertEqual(second["written"], [])
        self.assertEqual(second["failed"], [])
        self.assertEqual(len(self.written()), 2, "a repeated add wrote an assessment twice")

    def test_a_file_left_by_an_older_version_is_not_written(self):
        self.put("it-1.json", assessment("it-1", "DEV-1"))
        self.put("it-1.nolink.json", assessment("it-1"))     # left in out/ by review.py 0.18.0
        self.add()
        self.assertEqual([r["iteration_id"] for r in self.written()], ["it-1"])

    def test_an_assessment_already_in_the_daemon_is_skipped_by_its_key(self):
        self.put("it-1.json", assessment("it-1"))
        self.put("task-DEV-1.json", assessment(task="DEV-1"))
        self.add()
        other = Path(self.tmp.name) / "other-cycle"           # a new cycle directory with the same outputs
        shutil.copytree(self.dir / "out", other / "out")
        result = self.add(other)
        self.assertEqual(result["written"], [])
        self.assertEqual(sorted(r["file"].rsplit("/", 1)[1] for r in result["skipped"]), ["it-1.json", "task-DEV-1.json"])
        self.assertEqual(len(self.written()), 2)


if __name__ == "__main__":
    unittest.main()
