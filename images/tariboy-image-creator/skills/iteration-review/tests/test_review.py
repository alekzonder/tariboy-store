#!/usr/bin/env python3
"""Checks of the review cycle selection: `review.py candidates` and `coverage` on fixed rows."""
import importlib.util
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


def old(agent, n, day, **kw):
    """An iteration that ended in October, long before the window, and has only an older rubric assessment."""
    return it(agent, n, 0, ended_at=f"2026-10-{day:02d}T10:00:00Z", reassess=True, **kw)


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


    def test_reassessment_comes_after_the_window_problems_first_then_pairs(self):
        rows = [it("a", 1, 1), it("a", 2, 2, assessed=True)]
        rows += [old("a", 50 + n, 25 - n) for n in range(3)]                    # days old, only /1
        rows += [old("b", 50, 28, status="timeout"), old("b", 51, 20)]
        summary, picked = run("candidates", rows, "--reassess")
        self.assertEqual([r["id"] for r in picked], ["a-1", "b-50", "a-50", "b-51", "a-51", "a-52"])
        self.assertEqual([bool(r.get("reassess")) for r in picked], [False] + [True] * 5)
        self.assertEqual(picked[1]["reason"], "problem")
        self.assertEqual(summary["reassess"]["picked"], 5)
        self.assertEqual(summary["skipped"]["older_than_window"], 0)

    def test_reassessment_shares_the_sample_size_and_stays_off_without_the_flag(self):
        rows = [it("a", n, n) for n in range(1, 4)] + [old("a", 50 + n, 10 + n) for n in range(5)]
        summary, picked = run("candidates", rows, "--reassess", "--size", "5")
        self.assertEqual(len(picked), 5)
        self.assertEqual(sum(bool(r.get("reassess")) for r in picked), 2)
        self.assertEqual(summary["skipped"]["over_sample"], 3)
        summary, picked = run("candidates", rows)
        self.assertEqual([r["id"] for r in picked], ["a-3", "a-2", "a-1"])
        self.assertFalse(summary["reassess"]["on"])


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


def assessment(iteration="", task="", rubric="iteration-review/2"):
    obj = {"rubric_version": "iteration-review/2", "summary": "ok",
           "axes": [{"axis": a, "verdict": "scored", "score": 80} for a in ("image_process", "role", "task_fit")]}
    obj["rubric_version"] = rubric
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

    def test_an_older_rubric_assessment_does_not_block_the_new_one(self):
        old = dict(assessment("it-1", rubric="iteration-review/1"), id="as-old", assessor_agent="reviewer-1")
        self.db.write_text(json.dumps([old]))
        self.put("it-1.json", assessment("it-1"))
        result = self.add()
        self.assertEqual(len(result["written"]), 1)
        self.assertEqual([r["rubric_version"] for r in self.written()], ["iteration-review/1", "iteration-review/2"])

    def test_an_assessment_of_an_older_rubric_is_invalid(self):
        self.put("it-1.json", assessment("it-1", rubric="iteration-review/1"))
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "validate", "--dir", str(self.dir)],
                              capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("rubric_version must be iteration-review/2", proc.stdout)


def load_review():
    spec = importlib.util.spec_from_file_location("review", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Pack(unittest.TestCase):
    """Packs keep the whole transcript: no clipped entry, no cut middle; a pack larger than the window is read in parts."""

    def setUp(self):
        self.r = load_review()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def transcript(self, calls):
        self.r.tb = lambda *args, check=True: {"calls": calls}
        return self.r.transcript_lines("a", "a-1")

    def test_a_long_command_output_is_kept_whole_and_wrapped(self):
        output = "ok\n" + "x" * 5000 + "TAIL-MARK\nlast line"
        lines = self.transcript([{"seq": 7, "status": "ok", "delta": [{"role": "user", "blocks": [
            {"type": "tool_result", "text": output}]}], "response": {"blocks": [
            {"type": "tool_use", "tool_name": "Bash", "input": {"command": "cat big.log"}}]}}])
        text = [line for _, line in lines]
        self.assertEqual(text[0], "[seq 7] result:")
        self.assertTrue(all(len(line) <= self.r.LINE_CHARS for line in text))
        joined = "".join(line[2:] for line in text[1:text.index("[seq 7] call Bash:")])
        self.assertEqual(joined, output.replace("\n", ""))
        self.assertIn("  command: cat big.log", text)

    def test_skill_text_and_reminders_after_the_start_stay_in_the_transcript(self):
        lines = self.transcript([{"seq": 9, "status": "ok", "delta": [{"role": "user", "blocks": [
            {"type": "text", "text": "<system-reminder>The user said stop</system-reminder>"}]}]}])
        self.assertIn("  <system-reminder>The user said stop</system-reminder>", [x for _, x in lines])

    def test_a_subagent_conversation_repeated_in_every_delta_is_shown_once_and_marked(self):
        convo = [{"role": "user", "blocks": [{"type": "text", "text": "Assess pack P"}]},
                 {"role": "user", "blocks": [{"type": "tool_result", "tool_use_id": "t1", "text": "pack text"}]}]
        calls = [{"seq": 4, "model": "haiku", "delta": convo[:1], "response": {"blocks": [
                     {"type": "tool_use", "tool_use_id": "t1", "tool_name": "Read", "input": {"file_path": "P"}}]}},
                 {"seq": 5, "model": "haiku", "delta": convo, "response": {"blocks": [{"type": "text", "text": "done"}]}},
                 {"seq": 6, "model": "opus", "delta": [{"role": "user", "blocks": [
                     {"type": "tool_result", "tool_use_id": "t9", "text": "agent result"}]}]}]
        text = [x for _, x in self.transcript(calls)]
        self.assertEqual(text.count("  Assess pack P"), 1)
        self.assertEqual(text.count("  pack text"), 1)
        self.assertIn("[seq 5] subagent haiku result:", text)
        self.assertIn("[seq 6] result:", text)

    def body(self, n, width=300):
        lines = []
        for seq in range(1, n + 1):
            lines += self.r.entry(seq, "result:", f"line {seq} " + "y" * width)
        return lines

    def test_a_pack_inside_the_window_is_one_file_with_its_end_mark(self):
        job = self.r.write_pack(self.dir, "a-1", "# Iteration pack a-1\n\n", self.body(10), 100000, self.dir / "out" / "a-1.json")
        self.assertEqual(job["kind"], "pack")
        text = Path(job["pack"]).read_text()
        self.assertTrue(text.rstrip().endswith("-- end of pack a-1 --"))
        self.assertIn("line 5 ", text)

    def test_a_pack_over_the_window_is_split_in_seq_order_and_drops_nothing(self):
        head = "# Iteration pack a-1\n\nHEAD-MARK\n"
        body = self.body(400)
        job = self.r.write_pack(self.dir, "a-1", head, body, 30000, self.dir / "out" / "a-1.json")
        self.assertEqual(job["kind"], "parts")
        parts = job["parts"]
        self.assertGreater(len(parts), 3)
        seen = []
        for k, p in enumerate(parts, 1):
            text = Path(p["pack"]).read_text()
            self.assertLessEqual(len(text), 30000)
            self.assertTrue(text.startswith(head))
            self.assertIn(f"## Part {k} of {len(parts)}", text)
            seen += [x for x in text.splitlines() if x.startswith("[seq ") or x.startswith("  line ")]
            self.assertEqual(p["notes_in"] is None, k == 1)
            self.assertEqual(p["out"] is not None, k == len(parts))
        self.assertEqual(seen, [line for _, line in body])
        self.assertTrue((self.dir / "packs" / "a-1.parts.json").exists())

    def test_small_packs_share_a_subagent_only_while_they_fill_half_the_window(self):
        jobs = [{"kind": "pack", "id": f"a-{i}", "pack": f"p{i}", "out": f"o{i}", "chars": c}
                for i, c in enumerate([20000, 20000, 30000, 70000, 10000])]
        jobs.append({"kind": "parts", "id": "a-9", "parts": [], "out": "o9"})
        batches = self.r.batch_jobs(jobs, 100000)
        self.assertEqual([[p["id"] for p in b["pairs"]] if b["kind"] == "whole" else b["id"] for b in batches],
                         [["a-0", "a-1"], ["a-2"], ["a-3"], ["a-4"], "a-9"])


class Parts(unittest.TestCase):
    """`validate` accepts the assessment of a pack read in parts only when every earlier part left valid notes."""

    def setUp(self):
        self.r = load_review()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        body = []
        for seq in range(1, 200):
            body += self.r.entry(seq, "result:", "z" * 400)
        self.job = self.r.write_pack(self.dir, "a-1", "# Iteration pack a-1\n", body, 30000, self.dir / "out" / "a-1.json")
        (self.dir / "out").mkdir()
        (self.dir / "out" / "a-1.json").write_text(json.dumps(assessment("a-1")))

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "validate", "--dir", str(self.dir)],
                              capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def notes(self, k, n, **kw):
        obj = {"rubric_version": "iteration-review/2", "part": k, "of": n, "parts_read": list(range(1, k + 1)),
               "violations": [], "observations": [{"axis": "task_fit", "locator": "seq 3", "note": "asked first"}], "infra": []}
        obj.update(kw)
        return obj

    def write_notes(self, part=None, **kw):
        n = len(self.job["parts"])
        path = Path(self.job["parts"][-1]["notes_in"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.notes(part or n - 1, n, **kw)))

    def test_one_notes_file_is_read_and_written_by_every_part_but_the_last(self):
        parts = self.job["parts"]
        notes = {p["notes_out"] for p in parts[:-1]} | {p["notes_in"] for p in parts[1:]}
        self.assertEqual(len(notes), 1)
        self.assertIsNone(parts[0]["notes_in"])
        self.assertIsNone(parts[-1]["notes_out"])

    def test_notes_after_the_part_before_the_last_make_the_assessment_valid(self):
        self.write_notes()
        code, report = self.validate()
        self.assertEqual(code, 0, report)

    def test_missing_notes_make_the_assessment_invalid(self):
        code, report = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("notes of parts 1 to", json.dumps(report))

    def test_notes_that_stopped_at_an_earlier_part_make_the_assessment_invalid(self):
        self.write_notes(part=1)
        code, report = self.validate()
        self.assertEqual(code, 1)

    def test_notes_that_do_not_list_every_part_read_are_invalid(self):
        self.write_notes(parts_read=[1])
        code, report = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("no part is skipped", json.dumps(report))

    def test_an_assessment_that_leaves_out_a_violation_of_the_notes_is_invalid(self):
        push = {"axis": "image_process", "description": "pushed to main", "quote": "git push origin HEAD:main",
                "evidence": {"kind": "transcript", "iteration_id": "a-1", "locator": "seq 64"}}
        self.write_notes(violations=[push])
        code, report = self.validate()
        self.assertEqual(code, 1)
        self.assertIn("image_process at seq 64", json.dumps(report))
        (self.dir / "out" / "a-1.json").write_text(json.dumps(dict(assessment("a-1"), violations=[push])))
        code, report = self.validate()
        self.assertEqual(code, 0, report)


class RubricTransport(unittest.TestCase):
    """The rubric is prose for a model reader; these checks pin the two rules that must not be penalized."""
    RUBRIC = (Path(__file__).resolve().parent.parent / "rubric.md").read_text()

    def section(self):
        head = "## Not violations"
        self.assertIn(head, self.RUBRIC, "rubric lacks a 'Not violations' section")
        body = self.RUBRIC.split(head, 1)[1]
        return body.split("\n## ", 1)[0].lower()

    def test_a_file_or_a_quoted_heredoc_is_not_a_violation(self):
        text = self.section()
        for word in ("--file", "--body-file", "git commit -f", "quoted heredoc", "agents.md", "stdin"):
            self.assertIn(word, text)

    def test_the_form_of_the_final_chat_text_is_not_a_violation(self):
        text = self.section()
        for word in ("final text", "lists", "bold"):
            self.assertIn(word, text)

    def test_other_rules_stay_in_force(self):
        text = self.section()
        self.assertIn("only these two", text)
        self.assertIn("inline python", text)


DATA = {"date": "2026-11-05",
        "violations": [{"assessment_id": f"as-{n}", "iteration_id": f"it-{n}", "task_key": "", "agent": "dev", "image": "dev:1",
                        "axis": "image_process", "description": "d", "quote": "q"} for n in range(1, 13)],
        "infra": [{"assessment_id": "as-20", "iteration_id": "it-20", "text": "exit 137"}],
        "open_tasks": [{"key": "IMPROVE-aa11", "queue": "IMPROVE", "title": "t", "status": "open"}]}


def cause(slug, route, ids, **kw):
    return dict({"cause": f"cause {slug}", "slug": slug, "route": route, "impact": "degraded",
                 "assessments": [f"as-{n}" for n in ids]}, **kw)


def triage(causes):
    with tempfile.TemporaryDirectory() as tmp:
        plan, data = Path(tmp) / "plan.json", Path(tmp) / "in.json"
        plan.write_text(json.dumps({"date": "2026-11-05", "causes": causes}))
        data.write_text(json.dumps(DATA))
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "triage-check", "--plan", str(plan), "--input", str(data)],
                              capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)


class TriageCheck(unittest.TestCase):
    def test_routes_and_priority(self):
        code, res = triage([cause("a", "improve", range(1, 11)), cause("b", "tariboyd", [11]),
                            cause("c", "tariboyd", [12], impact="work_lost"), cause("d", "infra", ["20"])])
        self.assertEqual(code, 0, res)
        got = {x["cause"]: (x["queue"], x["assignee"], x["priority"]) for x in res["create"]}
        self.assertEqual(got["cause a"], ("IMPROVE", "tariboy-image-creator", "P1"))
        self.assertEqual(got["cause b"], ("TARI", "tariboy-pm", "P2"))
        self.assertEqual(got["cause c"][2], "P1")
        self.assertNotIn("cause d", got)
        self.assertIn("infra and noise 1 (cause d, 1)", res["journal_line"])
        self.assertEqual(res["create"][0]["idempotency_key"], "triage-2026-11-05-a")

    def test_create_args_assign_first_and_retry_without_assignee_when_workflow_managed(self):
        code, res = triage([cause("a", "improve", [1]), cause("b", "tariboyd", [2])])
        self.assertEqual(code, 0, res)
        by = {x["cause"]: x for x in res["create"]}
        # First answer: the queue takes an assignee, the command carries it.
        improve = by["cause a"]
        self.assertEqual(improve["create_args"], ["ttasks", "create", "--queue", "IMPROVE", "--assignee", "tariboy-image-creator",
                                                  "--priority", "P2", "--idempotency-key", "triage-2026-11-05-a"])
        # workflow_managed answer: the same command without --assignee, same key, so the retry is safe.
        self.assertEqual(improve["create_args_unassigned"], ["ttasks", "create", "--queue", "IMPROVE",
                                                             "--priority", "P2", "--idempotency-key", "triage-2026-11-05-a"])
        self.assertNotIn("--assignee", improve["create_args_unassigned"])
        tari = by["cause b"]
        self.assertEqual(tari["create_args"][4:6], ["--assignee", "tariboy-pm"])
        self.assertEqual([a for a in tari["create_args"] if a != "--assignee" and a != "tariboy-pm"], tari["create_args_unassigned"])

    def test_skill_documents_the_workflow_managed_retry(self):
        text = (SCRIPT.parent.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("workflow_managed", text)
        self.assertIn("create_args_unassigned", text)

    def test_duplicate_needs_an_open_task(self):
        code, res = triage([cause("a", "improve", [1], duplicate_of="IMPROVE-aa11")])
        self.assertEqual((code, res["create"]), (0, []))
        self.assertIn("duplicates IMPROVE-aa11 (cause a, 1)", res["journal_line"])
        code, res = triage([cause("a", "improve", [1], duplicate_of="IMPROVE-zzzz")])
        self.assertEqual(code, 1)

    def test_limit_of_five(self):
        causes = [cause(f"c{n}", "improve", [n]) for n in range(1, 7)]
        self.assertEqual(triage(causes)[0], 1)
        causes[5]["over_limit"] = True
        code, res = triage(causes)
        self.assertEqual((code, len(res["create"])), (0, 5))
        self.assertIn("candidates over limit 1 (cause c6, 1)", res["journal_line"])

    def test_unknown_assessment_or_route_is_refused(self):
        self.assertEqual(triage([cause("a", "improve", [99])])[0], 1)
        self.assertEqual(triage([cause("a", "devqueue", [1])])[0], 1)


if __name__ == "__main__":
    unittest.main()
