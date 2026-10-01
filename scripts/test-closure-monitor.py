#!/usr/bin/env python3
"""Deterministic contract check for the image-creator closure monitor.

It never talks to a daemon. A fake Scripts launcher keeps a JSON ledger and
applies the documented recurring-definition semantics (only the quiet exit
keeps a definition active), and a fake poll command plays the poll interface.
The check proves that the skill's schedule template, its lifecycle table and
the image instructions agree with each other and with that model; it is not
evidence of agent behavior.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = os.path.join(ROOT, "images", "tariboy-image-creator")
SKILL = os.path.join(IMAGE, "skills", "tariboy-image-delivery", "SKILL.md")
INSTRUCTIONS = os.path.join(IMAGE, "instructions.md")

FAKE_SCRIPTS = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
ledger = os.environ["FAKE_LEDGER"]
state = json.load(open(ledger)) if os.path.exists(ledger) else {"defs": {}, "next": 1, "outbox": []}
def save():
    json.dump(state, open(ledger, "w"))
cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "schedule":
    name, rest = args[0], args[1:]
    sep = rest.index("--")
    opts, command = rest[:sep], rest[sep + 1:]
    every = int(opts[opts.index("--every") + 1])
    quiet = int(opts[opts.index("--quiet-exit") + 1]) if "--quiet-exit" in opts else None
    sid = "scr-fake-%06d" % state["next"]
    state["next"] += 1
    state["defs"][sid] = {"name": name, "every": every, "quiet": quiet, "command": command, "state": "active"}
    save(); print(json.dumps({"script_id": sid}))
elif cmd == "ls":
    print(json.dumps(state["defs"]))
elif cmd == "tick":
    d = state["defs"][args[0]]
    if d["state"] != "active":
        sys.exit("not active")
    rc = subprocess.run(d["command"]).returncode
    if rc != d["quiet"]:
        d["state"] = "completed"
        state["outbox"].append({"script_id": args[0], "exit": rc})
    save(); print(rc)
elif cmd == "rerun":
    d = state["defs"].get(args[0])
    if d is None or d["state"] == "cancelled":
        sys.exit("not found")
    d["state"] = "active"; save()
elif cmd == "cancel":
    state["defs"][args[0]]["state"] = "cancelled"; save()
elif cmd == "rm":
    if args[0] not in state["defs"]:
        sys.exit("not found")
    del state["defs"][args[0]]; save()
else:
    sys.exit("unknown command " + cmd)
'''

FAKE_POLL = r'''#!/usr/bin/env python3
import json, os, sys
review, state_dir = sys.argv[1], sys.argv[sys.argv.index("--state-dir") + 1]
scenario = open(os.path.join(state_dir, "scenario")).read().strip()
codes = {"unchanged": 2, "open": 0, "closed": 0, "merged": 0, "data-error": 3, "missing-credential": 4}
if scenario in ("open", "closed", "merged"):
    facts = {"review": review, "state": scenario}
    if scenario == "merged":
        facts["merge_commit"] = "9c1e2f7"
    print(json.dumps(facts))
sys.exit(codes[scenario])
'''

# Result row of the skill's lifecycle table -> fake poll scenario.
RESULT_ROWS = {
    "review open": ["open"],
    "closed without merge": ["closed"],
    "data, parse, API or state error": ["data-error"],
    "missing credential, tool or dependency": ["missing-credential"],
    "merged with merge-commit metadata": ["merged"],
}


def read(path):
    with open(path) as handle:
        return handle.read()


def section(text, heading):
    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError("missing section: " + heading)
    return match.group(1)


def table_rows(text):
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2 and not set(cells[0]) <= set("- "):
            rows[cells[0]] = cells[-1]
    return rows


class ClosureMonitorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL)
        cls.closure = section(cls.skill, "Closure monitor")
        cls.instructions = read(INSTRUCTIONS)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.launcher = self.write_exec("scripts.sh", FAKE_SCRIPTS)
        self.poll = self.write_exec("closure-poll.sh", FAKE_POLL)
        self.state_dir = os.path.join(self.tmp.name, "review-state")
        os.mkdir(self.state_dir, 0o700)
        self.env = dict(os.environ, FAKE_LEDGER=os.path.join(self.tmp.name, "ledger.json"))

    def reset_ledger(self):
        if os.path.exists(self.env["FAKE_LEDGER"]):
            os.remove(self.env["FAKE_LEDGER"])

    def write_exec(self, name, body):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w") as handle:
            handle.write(body)
        os.chmod(path, 0o700)
        return path

    def scripts(self, *args):
        result = subprocess.run([sys.executable, self.launcher, *args], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def scenario(self, name):
        with open(os.path.join(self.state_dir, "scenario"), "w") as handle:
            handle.write(name)

    def template(self):
        blocks = re.findall(r"```text\n(scripts/scripts\.sh schedule .*?)\n```", self.closure)
        self.assertEqual(len(blocks), 1, "exactly one schedule template in ## Closure monitor")
        return shlex.split(blocks[0])

    def schedule_from_template(self):
        words = self.template()
        poll = [self.poll, "5512", "--state-dir", self.state_dir]
        built = []
        for word in words[1:]:
            if word == "NAME":
                built.append("review-monitor-img-140")
            elif word == "ABSOLUTE_POLL_COMMAND":
                built.extend(poll)
            elif word != "ARGS":
                built.append(word)
        sid = json.loads(self.scripts(*built))["script_id"]
        return sid, poll

    def ls(self):
        return json.loads(self.scripts("ls"))

    def test_skill_wiring_in_manifest_and_lock(self):
        manifest = read(os.path.join(IMAGE, "Tariboyfile.yaml"))
        lock = json.loads(read(os.path.join(IMAGE, "skills-lock.json")))["skills"]
        for name in ("scripts", "tariboy-image-delivery", "github-pr-workflow"):
            self.assertIn("- dir: ./.agents/skills/%s\n" % name, manifest)
            self.assertEqual(lock[name]["sourceType"], "local")
            self.assertTrue(os.path.isfile(os.path.join(IMAGE, lock[name]["source"], "SKILL.md")), name)
        self.assertRegex(manifest, r"(?m)^\s+- name: scripts$")

    def test_template_uses_owning_launcher_with_fixed_cadence(self):
        words = self.template()
        self.assertEqual(words[:3], ["scripts/scripts.sh", "schedule", "NAME"])
        self.assertEqual(words[3:8], ["--every", "60", "--quiet-exit", "2", "--"])
        github = re.findall(r"scripts/scripts\.sh schedule \S+ --every 60 --quiet-exit 2 -- \S+ monitor", self.skill)
        self.assertEqual(len(github), 1, "GitHub lifecycle keeps its own schedule template")

    def test_saved_command_is_identical_and_active(self):
        sid, poll = self.schedule_from_template()
        definition = self.ls()[sid]
        self.assertEqual(definition["command"], poll)
        self.assertEqual((definition["every"], definition["quiet"], definition["state"]), (60, 2, "active"))

    def test_unchanged_observation_is_quiet_and_keeps_running(self):
        sid, _ = self.schedule_from_template()
        self.scenario("unchanged")
        for _ in range(3):
            self.assertEqual(self.scripts("tick", sid).strip(), "2")
        self.assertEqual(self.ls()[sid]["state"], "active")
        with open(self.env["FAKE_LEDGER"]) as handle:
            self.assertEqual(json.load(handle)["outbox"], [])

    def test_lifecycle_table_matches_published_results(self):
        rows = table_rows(self.closure)
        for row, scenarios in RESULT_ROWS.items():
            self.assertIn(row, rows)
            action = rows[row]
            for name in scenarios:
                with self.subTest(result=name):
                    self.reset_ledger()
                    sid, _ = self.schedule_from_template()
                    self.scenario(name)
                    self.assertNotEqual(self.scripts("tick", sid).strip(), "2", "never quiet")
                    self.assertEqual(self.ls()[sid]["state"], "completed")
                    if "`rm SCRIPT_ID`" in action:
                        self.assertIn("never `rerun`", action)
                        if name == "merged":
                            self.assertIn("authoritative read", action)
                        self.scripts("rm", sid)
                        self.assertNotIn(sid, self.ls())
                    else:
                        self.assertIn("`rerun SCRIPT_ID`", action)
                        self.scripts("rerun", sid)
                        self.assertEqual(list(self.ls()), [sid], "resumed, not replaced")
                        self.assertEqual(self.ls()[sid]["state"], "active")
        interrupted = [r for r in rows if r.startswith("run interrupted")]
        self.assertEqual(len(interrupted), 1)
        self.assertIn("`rerun SCRIPT_ID`", rows[interrupted[0]])
        self.assertIn("cancel SCRIPT_ID` before `rm` only while `ls` still\nreports `state: active`", self.closure)

    def test_recovery_reuses_resumes_or_replaces_once(self):
        rows = table_rows(self.closure)
        self.assertIn("never schedule a second", rows["`ls` reports `state: active`"])
        self.assertIn("exactly one", rows["absent from `ls` while the review is open"])
        sid, poll = self.schedule_from_template()
        self.scripts("rm", sid)
        new_sid, _ = self.schedule_from_template()
        self.assertEqual([d["command"] for d in self.ls().values()], [poll])
        self.assertNotEqual(new_sid, sid)

    def test_instructions_agree_with_skill_lifecycle(self):
        text = self.instructions
        self.assertIn("| `scripts` | REQUIRED for the closure monitor in every completion mode |", text)
        row6 = re.search(r"^\| 6 \|.*$", text, re.M).group(0)
        row7 = re.search(r"^\| 7 \|.*$", text, re.M).group(0)
        for row in (row6, row7):
            self.assertIn("`tariboy-image-delivery`", row)
            self.assertIn("`scripts`", row)
            self.assertIn("`github-pr-workflow` when applicable", row)
        self.assertIn("re-read authoritatively", row6)
        self.assertIn("`rerun`", row6)
        self.assertIn("authoritative re-read confirms it", row7)
        self.assertIn("removed (cancelled first only while active)", row7)
        self.assertIn("row 7 never\nwaits for an answer", text)
        self.assertIn("closure monitor for the one PR or review request", section(text, "Waits and recovery"))


if __name__ == "__main__":
    unittest.main()
