#!/usr/bin/env python3
"""Review cycle helper for the iteration-review skill.

Subcommands (all JSON on stdout, diagnostics on stderr):
  cost       --agent NAME --since TIME            total cost of the cycle so far
  candidates --dir DIR --agents A,B --since TIME --assessor NAME [--window S] [--size N] [--reassess]
             the cycle's selection: last 24 h, not idle, problems first, then even over agent x image version, at most N;
             with --reassess, then iterations that have only an older rubric assessment of this assessor
  coverage   --agents A,B --since TIME --assessor NAME [--window S]
             metric 1: finished not idle iterations of the window, assessed ones, pairs with an assessment;
             and the re-assessment state: objects with an older rubric assessment, done and left
  pack       --dir DIR [--limit N] [--window-chars C]
             full evidence packs for the next N candidates, as assessor jobs: a batch of whole packs or one pack in parts
  tasks      --dir DIR --assessor NAME [--reassess] [--window-chars C]
             done tasks that are ready for a task assessment, as assessor jobs
  validate   --dir DIR                            check every DIR/out/*.json and its parts notes before it is written
  add        --dir DIR [--assessor NAME]          write every valid assessment the assessor has not written yet
  triage-input --assessor NAME [--out FILE] [--window S]
             the violations and `infra:` lines of this assessor's last 24 h, with the open tasks of IMPROVE and TARI
  triage-check --plan FILE --input FILE
             check a triage plan against that input; print the tasks to create and the journal line

Only `add` writes to the daemon (`tariboy assessment add`). Everything else reads.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RUBRIC = "iteration-review/2"
OLD_RUBRICS = ("iteration-review/1",)  # an object with only these from the assessor is re-assessed
AXES = ("image_process", "role", "task_fit")
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9a-z]{4}\b|\b[A-Z][A-Z0-9]*-[0-9]+\b")
INFRA_CODES = {137}  # 143 (SIGTERM) is the normal end after `loop.sh done`
WINDOW_CHARS = 240000  # what one assessor subagent reads: a whole pack, a batch of packs, or one part
BATCH_SHARE = 0.5      # several packs go to one subagent only while together they fill at most half of it
LINE_CHARS = 1000      # longer lines are wrapped, never cut: the Read tool shortens very long lines


def tb(*args, check=True):
    """Run the tariboy CLI with --json and return parsed output."""
    proc = subprocess.run(["tariboy", *args, "--json"], capture_output=True, text=True)
    if proc.returncode != 0:
        if check:
            sys.exit(f"tariboy {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        if check:
            sys.exit(f"tariboy {' '.join(args)}: output is not JSON")
        return None


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def clip(text, n):
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 15] + " …[clipped]"


# ---------------------------------------------------------------- cost

def cmd_cost(a):
    data = tb("usage", "--agent", a.agent, "--since", a.since)
    out({"since": a.since, "cost_usd": round(data.get("total_cost_usd", 0.0), 4),
         "requests": data.get("total_requests", 0)})


# ---------------------------------------------------------------- candidates

def prompt_sections(text):
    """Split PROMPT.md into top-level `# ` sections keyed by heading."""
    sections, head, buf = {}, "", []
    for line in text.splitlines():
        if line.startswith("# ") and not line.startswith("# ["):
            sections.setdefault(head, "\n".join(buf))
            head, buf = line[2:].strip(), []
        elif line.startswith("# ["):
            sections.setdefault(head, "\n".join(buf))
            head, buf = line.strip(), []
        else:
            buf.append(line)
    sections.setdefault(head, "\n".join(buf))
    return sections


def task_key_of(prompt):
    """Goal task first, then the first task key named by a delivered letter."""
    order = prompt.split("# [runtime: identity]")[0]
    goal = order.split("## Goal", 1)[1] if "## Goal" in order else ""
    m = re.search(r"^key:\s*(\S+)", goal, re.M)
    if m:
        return m.group(1), "goal"
    m = re.search(r'"task_key":"([^"]+)"', order)
    if m:
        return m.group(1), "letter"
    return "", ""


def has_assessment(assessor, iteration="", task=""):
    """True when the assessor already wrote an assessment of this iteration, or of this whole task, by RUBRIC.

    An assessment by an older rubric does not count: that object stays a candidate for RUBRIC.
    """
    args = ["assessment", "ls", "--assessor", assessor, "--limit", "1000"]
    args += ["--iteration", iteration] if iteration else ["--task", task]
    rows = [r for r in (tb(*args) or {}).get("assessments") or [] if r.get("rubric_version") == RUBRIC]
    if iteration:
        return bool(rows)
    return any(not r.get("iteration_id") for r in rows)


def reassess_state(assessor, agents):
    """Objects of the assessor with an older rubric assessment: which have a RUBRIC one (done) and which not (left).

    Iterations are listed per assessed agent, task assessments once for the assessor; `truncated` is true when a
    listing reached the daemon's limit of 1000 rows, so the counts may be low.
    """
    rows, truncated = [], False
    for agent in [x.strip() for x in agents.split(",") if x.strip()]:
        got = (tb("assessment", "ls", "--assessor", assessor, "--agent", agent, "--limit", "1000", check=False) or {}).get("assessments") or []
        truncated |= len(got) >= 1000
        rows += [dict(r, _agent=agent) for r in got if r.get("iteration_id")]
    got = (tb("assessment", "ls", "--assessor", assessor, "--limit", "1000", check=False) or {}).get("assessments") or []
    truncated |= len(got) >= 1000
    rows += [r for r in got if not r.get("iteration_id")]
    old, new, agent_of = set(), set(), {}
    for r in rows:
        key = ("iteration", r["iteration_id"]) if r.get("iteration_id") else ("task", r.get("task_key", ""))
        if r.get("iteration_id"):
            agent_of[r["iteration_id"]] = r.get("_agent") or r.get("subject_agent", "")
        if r.get("rubric_version") == RUBRIC:
            new.add(key)
        elif r.get("rubric_version") in OLD_RUBRICS:
            old.add(key)
    done, left = old & new, old - new
    count = lambda keys, kind: sum(k[0] == kind for k in keys)
    return {"rubric": RUBRIC, "from": list(OLD_RUBRICS),
            "iterations": {"total": count(old, "iteration"), "done": count(done, "iteration"), "left": count(left, "iteration")},
            "tasks": {"total": count(old, "task"), "done": count(done, "task"), "left": count(left, "task")},
            "truncated": truncated,
            "_left_iterations": sorted((agent_of.get(k[1], ""), k[1]) for k in left if k[0] == "iteration"),
            "_left_tasks": sorted(k[1] for k in left if k[0] == "task")}


def public(state):
    return {k: v for k, v in state.items() if not k.startswith("_")}


def parse_time(text):
    """RFC 3339 with up to nanoseconds -> aware datetime; empty -> None."""
    if not text:
        return None
    text = text.strip().replace("Z", "+00:00")
    m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", text)
    if m:
        text = m.group(1) + ((m.group(2) or "")[:7]) + m.group(3)
    t = dt.datetime.fromisoformat(text)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CMD_RE = r"(?:^|[;&|(]\s*|\n\s*)(?:ttasks|tasks)\s+{}\b"


def transcript_problems(agent, iteration):
    """Problem marks from the transcript: a `ttasks ask`, an `advance` whose result says rejected."""
    data = tb("transcript", agent, iteration, check=False) or {}
    marks, advances = set(), set()
    for call in data.get("calls") or []:
        for msg in call.get("delta") or []:
            for b in msg.get("blocks") or []:
                if (b.get("type") == "tool_result" and b.get("tool_use_id") in advances
                        and re.search(r"\brejected\b", b.get("text") or "")):
                    marks.add("check_rejected")
        for b in (call.get("response") or {}).get("blocks") or []:
            if b.get("type") != "tool_use":
                continue
            cmd = str((b.get("input") or {}).get("command", "")) if isinstance(b.get("input"), dict) else ""
            if re.search(CMD_RE.format("ask"), cmd):
                marks.add("question")
            if re.search(CMD_RE.format("advance"), cmd):
                advances.add(b.get("tool_use_id"))
    return sorted(marks)


def is_idle(row):
    """An idle iteration ended with `loop.sh done --idle`: status done, not productive."""
    return row.get("status") == "done" and row.get("productive") is False


def problems_of(row):
    """Problem kinds of one iteration row, in the order the selection names them.

    An idle iteration (`loop.sh done --idle`: done, not productive) is not a problem.
    """
    found = []
    status = row.get("status") or ""
    if status not in ("done", "running", ""):
        found.append(status)  # harness_error, timeout, no_i_am_done: ended without `loop.sh done`
    found += [m for m in row.get("marks") or [] if m in ("check_rejected", "question")]
    return found


def in_window(rows, now, window):
    """Finished, not idle iterations that ended inside the window, with the skip counts of the others."""
    start = now - dt.timedelta(seconds=window)
    kept, skipped = [], {"running": 0, "idle": 0, "older_than_window": 0}
    for r in rows:
        if r.get("status") == "running":
            skipped["running"] += 1
            continue
        ended = parse_time(r.get("ended_at")) or parse_time(r.get("started_at"))
        if ended is None or ended < start or ended > now:
            if not r.get("assessed"):
                skipped["older_than_window"] += 1
            continue
        if is_idle(r):
            skipped["idle"] += 1
            continue
        kept.append(dict(r, _ended=ended))
    return kept, skipped, {"from": iso(start), "to": iso(now)}


def in_order(rows):
    """Problem iterations first, newest first; then round by round over the pairs agent x image version."""
    rows = [dict(r, problems=problems_of(r)) for r in rows]
    newest = lambda r: (r["_ended"], r["id"])
    problem = sorted((r for r in rows if r["problems"]), key=newest, reverse=True)
    rest = {}
    for r in rows:
        if not r["problems"]:
            rest.setdefault((r["agent"], r.get("image_version") or ""), []).append(r)
    rest = {p: sorted(v, key=newest, reverse=True) for p, v in rest.items()}
    # Pairs with the freshest iteration go first in every round.
    order = sorted(rest, key=lambda p: newest(rest[p][0]), reverse=True)
    sample, rnd = [], 0
    while any(rnd < len(v) for v in rest.values()):
        for pair in order:
            if rnd < len(rest[pair]):
                sample.append(dict(rest[pair][rnd], reason="pair_sample"))
        rnd += 1
    return [dict(r, reason="problem") for r in problem] + sample


def select(rows, now, window, size):
    """Pick the cycle's candidates from gathered iteration rows.

    Each row: agent, id, status, productive, ended_at, image_version, assessed, marks.
    1. Only finished iterations that ended in the last `window` seconds; older unassessed ones are skipped.
       Idle iterations are not taken. An already assessed iteration is never a candidate.
    2. Problem iterations first, newest first.
    3. Then the others round by round over the pairs agent x image_version, newest first inside a pair.
    4. Rows marked `reassess` (only an older rubric assessment of this assessor, any age) come after the window,
       in the same order: problems first, then round by round over the pairs.
    5. At most `size` candidates; the rest is left for the next cycle while it is inside the window.
    """
    reassess = [dict(r, _ended=parse_time(r.get("ended_at")) or parse_time(r.get("started_at")) or now)
                for r in rows if r.get("reassess") and not r.get("assessed")]
    kept, skipped, win = in_window([r for r in rows if not r.get("reassess")], now, window)
    skipped.update(assessed=0, over_sample=0)
    pairs = {}
    for r in kept:
        st = pairs.setdefault((r["agent"], r.get("image_version") or ""), {"total": 0, "assessed": 0, "open": []})
        st["total"] += 1
        if r.get("assessed"):
            skipped["assessed"] += 1
            st["assessed"] += 1
            continue
        st["open"].append(r)
    # The window first: its iterations stop being candidates after 24 hours. Re-assessment fills the rest.
    picked = in_order([r for st in pairs.values() for r in st["open"]])
    known = {r["id"] for r in picked}
    picked += [dict(r, reassess=True) for r in in_order(r for r in reassess if r["id"] not in known)]
    skipped["over_sample"] = max(0, len(picked) - size)
    picked = picked[:max(0, size)]
    planned = {}
    for r in picked:
        key = (r["agent"], r.get("image_version") or "")
        planned[key] = planned.get(key, 0) + 1
    out_rows = [{k: v for k, v in r.items() if not k.startswith("_") and k != "assessed"} for r in picked]
    pair_rows = [{"agent": a, "image_version": v, "iterations": st["total"], "assessed": st["assessed"],
                  "planned": planned.get((a, v), 0)} for (a, v), st in sorted(pairs.items())]
    return out_rows, skipped, pair_rows, win


def gather(agents, since, assessor, now, window, marks=True):
    """Iteration rows of the agents that may fall in the window, with assessment state and problem marks."""
    floor = now - dt.timedelta(seconds=window) - dt.timedelta(hours=6)  # an iteration may run hours before it ends
    since_t = parse_time(since)
    after = max(floor, since_t) if since_t else floor
    rows = []
    for agent in [x.strip() for x in agents.split(",") if x.strip()]:
        data = tb("iteration", "ls", agent, "--started-after", iso(after), check=False) or {}
        for it in data.get("iterations") or []:
            row = {"agent": agent, "id": it["id"], "status": it.get("status", ""), "started_at": it.get("started_at", ""),
                   "productive": it.get("productive")}
            if row["status"] == "running":
                rows.append(row)
                continue
            info = tb("iteration", "inspect", agent, it["id"], check=False) or {}
            info = info.get("iteration", info)
            row.update(ended_at=info.get("ended_at", ""), image_version=info.get("image_version", ""))
            ended = parse_time(row["ended_at"]) or parse_time(row["started_at"])
            if ended and ended < now - dt.timedelta(seconds=window):
                row["assessed"] = False
                rows.append(row)
                continue
            row["assessed"] = has_assessment(assessor, iteration=it["id"])
            prompt = ""
            try:
                prompt = Path(info.get("prompt_path", "")).read_text()
            except OSError:
                pass
            if agent == assessor and (info.get("trigger") == "schedule" or 'Script "review-cycle"' in prompt):
                continue  # the cycle's own iterations are not assessed
            row["task_key"], row["task_source"] = task_key_of(prompt)
            if marks and not row["assessed"]:
                row["marks"] = transcript_problems(agent, it["id"])
            rows.append(row)
    return rows


def gather_reassess(agents, assessor, known):
    """Rows of the iterations that only an older rubric assessment of this assessor covers, at any age."""
    state = reassess_state(assessor, agents)
    rows = []
    for agent, iteration in state["_left_iterations"]:
        if iteration in known or not agent:
            continue
        info = tb("iteration", "inspect", agent, iteration, check=False) or {}
        info = info.get("iteration", info)
        prompt = ""
        try:
            prompt = Path(info.get("prompt_path", "")).read_text()
        except OSError:
            pass
        row = {"agent": agent, "id": iteration, "status": info.get("status", ""), "started_at": info.get("started_at", ""),
               "ended_at": info.get("ended_at", ""), "productive": info.get("productive"),
               "image_version": info.get("image_version", ""), "assessed": False, "reassess": True}
        row["task_key"], row["task_source"] = task_key_of(prompt)
        row["marks"] = transcript_problems(agent, iteration)
        rows.append(row)
    return rows, state


def now_arg(a):
    return parse_time(a.now) if getattr(a, "now", None) else dt.datetime.now(dt.timezone.utc)


def cmd_candidates(a):
    d = Path(a.dir)
    now = now_arg(a)
    rows = read_json(a.input, []) if a.input else gather(a.agents, a.since, a.assessor, now, a.window)
    state = None
    if a.reassess and not a.input:
        extra, state = gather_reassess(a.agents, a.assessor, {r["id"] for r in rows})
        rows += extra
    if not a.reassess:
        rows = [r for r in rows if not r.get("reassess")]
    picked, skipped, pairs, window = select(rows, now, a.window, a.size)
    write_json(d / "candidates.json", picked)
    write_json(d / "pairs.json", pairs)
    summary = {"window": window, "sample_size": a.size, "candidates": len(picked),
               "problem": sum(r["reason"] == "problem" for r in picked), "skipped": skipped,
               "active_pairs": len(pairs), "file": str(d / "candidates.json"),
               "reassess": {"on": bool(a.reassess), "picked": sum(bool(r.get("reassess")) for r in picked)}}
    if state:
        summary["reassess"].update(public(state))
    out(summary)


def coverage(rows, now, window):
    """Metric 1 inputs: finished, not idle iterations of the window, how many have an assessment, and pairs."""
    kept, _, win = in_window(rows, now, window)
    pairs = {}
    for r in kept:
        st = pairs.setdefault((r["agent"], r.get("image_version") or ""), {"total": 0, "assessed": 0})
        st["total"] += 1
        st["assessed"] += bool(r.get("assessed"))
    total = sum(st["total"] for st in pairs.values())
    assessed = sum(st["assessed"] for st in pairs.values())
    with_one = [p for p, st in pairs.items() if st["assessed"] >= 1]
    return {"window": win, "iterations": total, "assessed_iterations": assessed,
            "assessed_share": round(assessed / total, 4) if total else None,
            "active_pairs": len(pairs), "pairs_with_assessment": len(with_one),
            "pairs": [{"agent": a, "image_version": v, **st} for (a, v), st in sorted(pairs.items())]}


def cmd_coverage(a):
    now = now_arg(a)
    rows = read_json(a.input, []) if a.input else gather(a.agents, a.since, a.assessor, now, a.window, marks=False)
    result = coverage([r for r in rows if not r.get("reassess")], now, a.window)
    if not a.input:
        result["reassess"] = public(reassess_state(a.assessor, a.agents))
    out(result)


# ---------------------------------------------------------------- pack

def role_md(image_ref, digest, version):
    """ROLE.md of the exact image digest, else of the Store commit with that image_version."""
    name = image_ref.split(":")[0]
    for ref in (f"{name}:{version}", image_ref, f"{name}:latest"):
        man = tb("image", "inspect", ref, check=False)
        if man and man.get("digest") == digest:
            text = (man.get("role") or {}).get("text", "")
            return (text, f"manifest {ref}@{digest[:12]}") if text else ("", f"manifest {ref} has no ROLE.md")
    path = f"images/{name}/Tariboyfile.yaml"
    log = subprocess.run(["git", "log", "--format=%H", "-G", f"^image_version: {re.escape(version)}$", "--", path],
                         capture_output=True, text=True)
    for commit in log.stdout.split():
        show = subprocess.run(["git", "show", f"{commit}:images/{name}/ROLE.md"], capture_output=True, text=True)
        if show.returncode == 0:
            return show.stdout, f"store commit {commit[:12]} (image_version {version})"
        return "", f"store commit {commit[:12]} has no ROLE.md"
    return "", "no manifest at this digest and no store commit with this image_version"


def wrap(text, indent=""):
    """The text as lines of at most LINE_CHARS characters. A longer line is wrapped, never cut."""
    lines = []
    for line in str(text or "").split("\n"):
        line = indent + line.rstrip("\r")
        while len(line) > LINE_CHARS:
            lines.append(line[:LINE_CHARS])
            line = indent + line[LINE_CHARS:]
        lines.append(line)
    return lines


def entry(seq, label, text=None):
    """One transcript entry: a `[seq N] label` line, then the full text indented by two spaces."""
    lines = [(seq, f"[seq {seq}] {label}")]
    if text is not None and str(text) != "":
        lines += [(seq, x) for x in wrap(text, "  ")]
    return lines


def input_text(value):
    """A tool call input as `key: value` lines; strings stay as they are, other values as JSON."""
    if not isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "\n".join(f"{k}: {v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}" for k, v in value.items())


def transcript_lines(agent, iteration):
    """The whole transcript as (seq, line) pairs in seq order: every call, result and text in full."""
    data = tb("transcript", agent, iteration, check=False)
    if data is None:
        return [(0, "Transcript: not readable, `tariboy transcript` failed.")]
    calls = data.get("calls") or []
    # The agent's own model is the model of its last call; calls of another model are subagents.
    main = next((c.get("model") for c in reversed(calls) if c.get("model")), "")
    lines, seen = [], set()

    def first(key):
        """A block that repeats one already shown word for word is shown once, at its first seq.

        The delta of a subagent call repeats that subagent's conversation, so without this a transcript grows many
        times over with copies. Nothing that was not shown before is left out.
        """
        if key in seen:
            return False
        seen.add(key)
        return True

    for call in calls:
        seq = call.get("seq")
        who = f"subagent {call.get('model')} " if call.get("model") and call.get("model") != main else ""
        if call.get("status") not in ("ok", None, "quota_probe"):
            lines += entry(seq, f"{who}API status {call.get('status')}")
        if call.get("truncated"):
            lines += entry(seq, "note: the AI proxy stored this call truncated")
        for msg in call.get("delta") or []:
            role = msg.get("role")
            for b in msg.get("blocks") or []:
                text = b.get("text") or ""
                if role == "user" and b.get("type") == "tool_result":
                    if first(("result", b.get("tool_use_id") or text)):
                        lines += entry(seq, f"{who}result:" if not b.get("is_error") else f"{who}result (error):", text)
                elif role in ("user", "system") and b.get("type") == "text" and seq and seq > 3:
                    if first((role, text)):
                        lines += entry(seq, f"{who}{role}:", text)
        for b in (call.get("response") or {}).get("blocks") or []:
            if b.get("type") == "tool_use":
                if first(("call", b.get("tool_use_id") or input_text(b.get("input")))):
                    lines += entry(seq, f"{who}call {b.get('tool_name')}:", input_text(b.get("input")))
            elif b.get("type") == "text":
                lines += entry(seq, f"{who}text:", b.get("text") or "")
    return lines


def task_block(key, agent):
    """The task in full: description, every comment and every event."""
    if not key:
        return "No task: the iteration had no goal task and no letter named one.\n"
    show = tb("tasks", "show", key, check=False)
    if not show:
        return f"Task {key}: not readable.\n"
    t = show.get("task", show)
    parts = [f"key: {key}", f"title: {t.get('title', '')}", f"status: {t.get('status', '')}",
             f"assignee: {t.get('assignee', '')}", f"created_at: {t.get('created_at', '')}",
             f"workflow: {t.get('workflow', '') or t.get('workflow_ref', '') or 'none'}",
             "description:", t.get("description", "") or "", "", "comments:"]
    for c in show.get("comments") or []:
        parts.append(f"- comment {c.get('id')} by {c.get('author')} at {c.get('created_at')}:")
        parts += wrap(c.get("body"), "  ")
    ev = tb("tasks", "events", "--key", key, check=False) or {}
    parts.append("")
    parts.append("events (sequence kind actor payload):")
    for e in ev.get("events") or []:
        parts.append(f"- {e.get('sequence')} {e.get('kind')} {e.get('actor')} {json.dumps(e.get('payload'), ensure_ascii=False)}")
    return "\n".join(parts) + "\n"


def split_body(head, body, window):
    """Split body lines into parts so that head plus one part fits `window` characters. No line is dropped."""
    budget = max(window - len(head) - 2000, window // 4)
    parts, cur, size = [], [], 0
    for seq, line in body:
        if cur and size + len(line) + 1 > budget:
            parts.append(cur)
            cur, size = [], 0
        cur.append((seq, line))
        size += len(line) + 1
    if cur or not parts:
        parts.append(cur)
    return parts


def seq_range(part):
    seqs = [s for s, _ in part if isinstance(s, int)]
    return (min(seqs), max(seqs)) if seqs else (None, None)


def write_pack(d, name, head, body, window, out_path):
    """Write one pack, whole or in parts, and return its assessor job.

    A whole pack: `packs/NAME.md`. A pack larger than `window`: `packs/NAME.part-KK.md`, each with the same head
    and the next lines of the body in seq order, and `packs/NAME.parts.json`, which `validate` reads.
    """
    pdir = d / "packs"
    pdir.mkdir(parents=True, exist_ok=True)
    text = "\n".join(line for _, line in body)
    if len(head) + len(text) + 200 <= window:
        p = pdir / f"{name}.md"
        content = f"{head}{text}\n\n-- end of pack {name} --\n"
        p.write_text(content)
        return {"kind": "pack", "id": name, "pack": str(p), "out": str(out_path), "chars": len(content)}
    parts = split_body(head, body, window)
    n = len(parts)
    job = {"kind": "parts", "id": name, "out": str(out_path), "parts": []}
    for k, part in enumerate(parts, 1):
        first, last = seq_range(part)
        cont = bool(part) and not part[0][1].startswith("[seq ")
        lines = [f"## Part {k} of {n}: seq {first} to seq {last}", ""]
        if cont:
            lines.append(f"(This part starts inside the entry of seq {first} that part {k - 1} began.)")
        lines += [line for _, line in part]
        p = pdir / f"{name}.part-{k:02d}.md"
        p.write_text(f"{head}" + "\n".join(lines) + f"\n\n-- end of part {k} of {n} of pack {name} --\n")
        notes = str(d / "notes" / f"{name}.json")  # one file: each part reads it and writes it back with its findings
        job["parts"].append({"part": k, "of": n, "pack": str(p), "seq": f"{first}-{last}",
                             "notes_in": notes if k > 1 else None,
                             "notes_out": notes if k < n else None,
                             "out": str(out_path) if k == n else None})
    write_json(pdir / f"{name}.parts.json", job)
    return job


def batch_jobs(jobs, window):
    """One subagent per job. Whole packs share one subagent only while together they fill at most BATCH_SHARE."""
    result, cur, size = [], [], 0
    limit = window * BATCH_SHARE
    for j in jobs:
        alone = j["kind"] != "pack" or j["chars"] > limit
        if cur and (alone or size + j["chars"] > limit):
            result.append({"kind": "whole", "pairs": cur, "chars": size})
            cur, size = [], 0
        if alone:
            result.append(j if j["kind"] == "parts" else {"kind": "whole", "pairs": [j], "chars": j["chars"]})
            continue
        cur.append(j)
        size += j["chars"]
    if cur:
        result.append({"kind": "whole", "pairs": cur, "chars": size})
    return [dict(j, pairs=[{k: p[k] for k in ("id", "pack", "out")} for p in j["pairs"]]) if j["kind"] == "whole" else j
            for j in result]


def packed_already(d, name):
    return any(x.exists() for x in (d / "packs" / f"{name}.md", d / "packs" / f"{name}.parts.json",
                                    d / "out" / f"{name}.json"))


def cmd_pack(a):
    d = Path(a.dir)
    cands = read_json(d / "candidates.json", [])
    jobs = []
    for c in cands:
        if len(jobs) >= a.limit:
            break
        if packed_already(d, c["id"]):
            continue
        info = tb("iteration", "inspect", c["agent"], c["id"], check=False) or {}
        info = info.get("iteration", info)
        res = read_json(Path(info.get("prompt_path", "/nonexistent")).parent / "result.json", {})
        prompt = ""
        try:
            prompt = Path(info.get("prompt_path", "")).read_text()
        except OSError:
            prompt = ""
        order = prompt.split("# [runtime: identity]")[0]
        instr = prompt.split("# [runtime: workdir]")[-1].split("# [runtime: user-prompt]")[0] if prompt else ""
        user = prompt.split("# [runtime: user-prompt]")[1].split("# Finishing this iteration")[0] if "# [runtime: user-prompt]" in prompt else ""
        role, role_src = role_md(info.get("image_ref", ""), info.get("image_digest", ""), info.get("image_version", ""))
        exit_code = res.get("exit_code", info.get("exit_code"))
        infra = []
        if exit_code in INFRA_CODES or res.get("oom"):
            infra.append(f"exit_code {exit_code}, oom {res.get('oom')}")
        if info.get("status") == "timeout":
            infra.append("status timeout")
        head = "\n".join([
            f"# Iteration pack {c['id']}",
            "",
            "## Iteration",
            f"agent: {c['agent']}",
            f"iteration_id: {c['id']}",
            f"status: {info.get('status')} trigger: {info.get('trigger')} productive: {info.get('productive')}",
            f"started_at: {info.get('started_at')} ended_at: {info.get('ended_at')}",
            f"exit_code: {exit_code} oom: {res.get('oom')}",
            f"image: {info.get('image_ref')} image_version: {info.get('image_version')} digest: {info.get('image_digest', '')[:12]}",
            f"task_key: {c.get('task_key') or 'none'} (from {c.get('task_source') or '-'})",
            f"infra signals: {'; '.join(infra) or 'none'}",
            "",
            "## Task",
            task_block(c.get("task_key"), c["agent"]),
            "## Iteration input (task order, letters, goal)",
            order.strip(),
            "",
            "## ROLE.md",
            f"source: {role_src}",
            role if role else "ABSENT: the axis `role` is `not_applicable`.",
            "",
            "## Image instructions of this version",
            instr.strip(),
            "",
            "## User prompt",
            user.strip() or "none",
            "",
            "## Transcript (locator = seq N)",
            "",
            "Every entry is in full; a line longer than 1000 characters is wrapped onto the next line.",
            "A block that repeats an earlier one word for word is shown once, at its first seq.",
            "`subagent MODEL` marks a call of a subagent the agent started, not of the agent itself.",
            "",
        ])
        head = "\n".join(wrap(head)) + "\n"
        job = write_pack(d, c["id"], head, transcript_lines(c["agent"], c["id"]), a.window_chars, d / "out" / f"{c['id']}.json")
        jobs.append(dict(job, agent=c["agent"], task_key=c.get("task_key", "")))
    remaining = sum(1 for c in cands if not packed_already(d, c["id"]))
    jobs = batch_jobs(jobs, a.window_chars)
    write_json(d / "batch.json", jobs)
    out({"jobs": jobs, "iterations": sum(len(j["pairs"]) if j["kind"] == "whole" else 1 for j in jobs),
         "subagents": sum(len(j["parts"]) if j["kind"] == "parts" else 1 for j in jobs),
         "remaining_unpacked": remaining})


# ---------------------------------------------------------------- tasks

def cmd_tasks(a):
    d = Path(a.dir)
    cands = read_json(d / "candidates.json", [])
    added = {r["file"] for r in read_json(d / "added.json", [])}
    open_iters = {}
    for c in cands:
        if c.get("task_key") and str(d / "out" / f"{c['id']}.json") not in added:
            open_iters.setdefault(c["task_key"], []).append(c["id"])
    keys = {c["task_key"] for c in cands if c.get("task_key")}
    if a.reassess:
        keys |= set(reassess_state(a.assessor, "")["_left_tasks"])
    jobs = []
    for key in sorted(keys):
        name = f"task-{key}"
        if open_iters.get(key) or packed_already(d, name) or has_assessment(a.assessor, task=key):
            continue
        show = tb("tasks", "show", key, check=False)
        t = (show or {}).get("task", show or {})
        if t.get("status") != "done":
            continue
        rows = (tb("assessment", "ls", "--task", key, "--limit", "1000", check=False) or {}).get("assessments") or []
        ev = (tb("tasks", "events", "--key", key, check=False) or {}).get("events") or []
        kinds = [e.get("kind", "") for e in ev]
        payloads = [json.dumps(e.get("payload"), ensure_ascii=False) for e in ev]
        head = "\n".join([f"# Task pack {key}", "", "Assess the whole task: write `task_key`, no `iteration_id`.", "", ""])
        lines = ["## Task", task_block(key, ""), "## Measures",
                 f"created_at: {t.get('created_at')}  done_at: {t.get('updated_at')}",
                 f"rework rounds (changes_requested or reopened): {sum(('changes_requested' in x) or ('reopen' in x) for x in kinds + payloads)}",
                 f"questions to the customer (task.question_asked or waits): {sum(('question' in k) or ('wait' in k) for k in kinds)}",
                 "", "## Iteration assessments of this task"]
        for r in rows:
            if r.get("iteration_id"):
                lines.append(f"- {r.get('id')} iteration {r.get('iteration_id')} rubric {r.get('rubric_version')}: {r.get('summary')}")
        body = [(None, x) for x in wrap("\n".join(lines))]
        jobs.append(dict(write_pack(d, name, head, body, a.window_chars, d / "out" / f"{name}.json"), task_key=key))
    jobs = batch_jobs(jobs, a.window_chars)
    write_json(d / "task-batch.json", jobs)
    out({"jobs": jobs, "tasks": sum(len(j["pairs"]) if j["kind"] == "whole" else 1 for j in jobs)})


# ---------------------------------------------------------------- validate / add

def check(obj):
    errs = []
    if obj.get("rubric_version") != RUBRIC:
        errs.append(f"rubric_version must be {RUBRIC}")
    if not obj.get("iteration_id") and not obj.get("task_key"):
        errs.append("needs iteration_id or task_key")
    if not str(obj.get("summary", "")).strip():
        errs.append("summary is empty")
    axes = obj.get("axes") or []
    if sorted(x.get("axis", "") for x in axes) != sorted(AXES):
        errs.append("axes must be image_process, role, task_fit, each once")
    for x in axes:
        v = x.get("verdict")
        if v == "scored":
            s = x.get("score")
            if not isinstance(s, int) or not 0 <= s <= 100:
                errs.append(f"{x.get('axis')}: score must be an integer 0..100")
        elif v == "not_applicable":
            if "score" in x:
                errs.append(f"{x.get('axis')}: not_applicable has no score")
        else:
            errs.append(f"{x.get('axis')}: verdict must be scored or not_applicable")
    errs += check_violations(obj.get("violations"))
    return errs


def check_violations(violations):
    errs = []
    if violations is None:
        violations = []
    if not isinstance(violations, list):
        return ["violations must be a list"]
    for i, v in enumerate(violations):
        if v.get("axis") not in AXES:
            errs.append(f"violation {i}: unknown axis")
        if not str(v.get("description", "")).strip() or not str(v.get("quote", "")).strip():
            errs.append(f"violation {i}: needs description and quote")
        ev = v.get("evidence") or {}
        kind = ev.get("kind")
        if kind == "transcript":
            if not ev.get("iteration_id") or not ev.get("locator"):
                errs.append(f"violation {i}: transcript evidence needs iteration_id and locator")
        elif kind == "task_event":
            if not ev.get("task_key") or not isinstance(ev.get("sequence"), int):
                errs.append(f"violation {i}: task_event evidence needs task_key and integer sequence")
        elif kind == "script_run":
            if not str(ev.get("run_id", "")).startswith("srun-"):
                errs.append(f"violation {i}: script_run evidence needs run_id srun-...")
        else:
            errs.append(f"violation {i}: evidence kind must be transcript, task_event or script_run")
    return errs


def check_notes(obj, part, of):
    """Notes of one part of a pack read in parts: the findings so far, see "Reading in parts" of the rubric."""
    errs = []
    if obj.get("rubric_version") != RUBRIC:
        errs.append(f"rubric_version must be {RUBRIC}")
    if obj.get("part") != part or obj.get("of") != of:
        errs.append(f"part and of must be {part} and {of}")
    if obj.get("parts_read") != list(range(1, part + 1)):
        errs.append(f"parts_read must be {list(range(1, part + 1))}: no part is skipped")
    errs += check_violations(obj.get("violations"))
    obs = obj.get("observations")
    if not isinstance(obs, list) or any(not isinstance(o, dict) or o.get("axis") not in AXES
                                        or not str(o.get("note", "")).strip() for o in obs):
        errs.append("observations must be a list of {axis, locator, note}")
    if not isinstance(obj.get("infra", []), list):
        errs.append("infra must be a list")
    return errs


def chain_errors(d, f, obj):
    """For a pack read in parts: the notes after part N-1 read every part before the last, and the assessment
    keeps every violation of the notes."""
    manifest = d / "packs" / f"{f.stem}.parts.json"
    if not manifest.exists():
        return []
    job = read_json(manifest, {})
    last = (job.get("parts") or [{}])[-1]
    n = last.get("of", 1)
    if n < 2 or not last.get("notes_in"):
        return []
    try:
        notes = json.loads(Path(last["notes_in"]).read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [f"notes of parts 1 to {n - 1} missing or not JSON: {e}"]
    errs = [f"notes: {x}" for x in check_notes(notes, n - 1, n)]
    final = {finding(v) for v in obj.get("violations") or []}
    errs += [f"violation {axis} at {loc} of the notes is not in the assessment"
             for axis, loc in {finding(v) for v in notes.get("violations") or []} if (axis, loc) not in final]
    return errs


def finding(v):
    """A violation by axis and locator: the assessment of the last part keeps every one the notes found."""
    ev = v.get("evidence") or {}
    return v.get("axis"), str(ev.get("locator") or ev.get("sequence") or ev.get("run_id") or "")


def out_files(d):
    """Assessor outputs in DIR/out. A `*.nolink.json` left there by review.py 0.18.0 or older is not an output."""
    return [f for f in sorted((d / "out").glob("*.json")) if not f.name.endswith(".nolink.json")]


def written_by(assessor, obj):
    """ID of an assessment this assessor already wrote for the same iteration, or the same whole task, and rubric."""
    if obj.get("iteration_id"):
        rows = (tb("assessment", "ls", "--assessor", assessor, "--iteration", obj["iteration_id"], "--limit", "1000") or {}).get("assessments") or []
    else:
        rows = (tb("assessment", "ls", "--assessor", assessor, "--task", obj["task_key"], "--limit", "1000") or {}).get("assessments") or []
        rows = [r for r in rows if not r.get("iteration_id")]
    rows = [r for r in rows if r.get("rubric_version") == obj.get("rubric_version")]
    return rows[0].get("id", "") if rows else ""


def cmd_validate(a):
    d = Path(a.dir)
    report = []
    for f in out_files(d):
        try:
            obj = json.loads(f.read_text())
            errs = check(obj) + chain_errors(d, f, obj)
        except json.JSONDecodeError as e:
            errs = [f"not JSON: {e}"]
        report.append({"file": str(f), "ok": not errs, "errors": errs})
    write_json(d / "validate.json", report)
    out({"valid": sum(r["ok"] for r in report), "invalid": [r for r in report if not r["ok"]]})
    if any(not r["ok"] for r in report):
        sys.exit(1)


def cmd_add(a):
    """Write each output once: skip a file this cycle wrote, and an assessment the daemon already has by
    assessor, rubric and iteration (or whole task). Retry files without task_key live outside out/."""
    d = Path(a.dir)
    if not a.assessor:
        sys.exit("add needs --assessor or TARIBOY_AGENT: the daemon records assessments under this agent")
    added = read_json(d / "added.json", [])
    done = {r["file"] for r in added}
    results = []
    for f in out_files(d):
        if str(f) in done:
            continue
        obj = json.loads(f.read_text())
        if check(obj) or chain_errors(d, f, obj):
            results.append({"file": str(f), "error": "invalid, run validate"})
            continue
        existing = written_by(a.assessor, obj)
        if existing:
            rec = {"file": str(f), "skipped": existing, "iteration_id": obj.get("iteration_id", ""),
                   "task_key": obj.get("task_key", ""), "note": "already written by this assessor"}
            added.append(rec)
            results.append(rec)
            write_json(d / "added.json", added)
            continue
        proc = subprocess.run(["tariboy", "assessment", "add", "--file", str(f), "--json"], capture_output=True, text=True)
        note = ""
        if proc.returncode != 0 and obj.get("iteration_id") and obj.get("task_key") and "link" in (proc.stderr + proc.stdout).lower():
            obj.pop("task_key")
            alt = d / "nolink" / f.name
            alt.parent.mkdir(parents=True, exist_ok=True)
            alt.write_text(json.dumps(obj, ensure_ascii=False))
            proc = subprocess.run(["tariboy", "assessment", "add", "--file", str(alt), "--json"], capture_output=True, text=True)
            note = "task_key dropped: iteration and task are not linked"
        if proc.returncode != 0:
            results.append({"file": str(f), "error": clip(proc.stderr or proc.stdout, 400)})
            continue
        row = json.loads(proc.stdout or "{}")
        row = row.get("assessment", row)
        rec = {"file": str(f), "id": row.get("id", ""), "iteration_id": obj.get("iteration_id", ""),
               "task_key": obj.get("task_key", ""), "note": note}
        added.append(rec)
        results.append(rec)
        write_json(d / "added.json", added)
    out({"written": [r for r in results if "id" in r], "skipped": [r for r in results if "skipped" in r],
         "failed": [r for r in results if "error" in r],
         "total_written_this_cycle": sum("id" in r for r in added)})
    if any("error" in r for r in results):
        sys.exit(1)


TRIAGE_LIMIT = 5              # new tasks one triage creates, all queues together
TRIAGE_QUEUES = {"improve": ("IMPROVE", "tariboy-image-creator"), "tariboyd": ("TARI", "tariboy-pm")}
TRIAGE_ROUTES = ("improve", "tariboyd", "infra", "noise")
TRIAGE_IMPACT = ("work_lost", "degraded", "none")


def cmd_triage_input(a):
    """Violations of the last 24 hours of one assessor, with the open tasks of IMPROVE and TARI."""
    now = parse_time(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    if a.input:
        data = read_json(a.input, {})
        rows, open_tasks = data.get("assessments", []), data.get("open_tasks", [])
    else:
        listing = tb("assessment", "ls", "--assessor", a.assessor, "--limit", "1000", "--history")
        rows = []
        for row in listing.get("assessments", []):
            when = parse_time(row.get("created_at", ""))
            if when is None or now - when > dt.timedelta(seconds=a.window) or not row.get("violation_count"):
                continue
            rows.append(tb("assessment", "show", row["id"])["assessment"])
        tasks = tb("tasks", "list", "--queue", "IMPROVE,TARI", "--limit", "500")
        open_tasks = [{"key": t.get("key"), "queue": t.get("queue"), "title": t.get("title"), "status": t.get("status")}
                      for t in tasks.get("tasks", [])]
    violations, infra = [], []
    for r in rows:
        for v in r.get("violations") or []:
            violations.append({"assessment_id": r["id"], "iteration_id": r.get("iteration_id", ""), "task_key": r.get("task_key", ""),
                               "agent": r.get("subject_agent", ""), "image": f"{r.get('image_ref', '')}:{r.get('image_version', '')}",
                               "axis": v.get("axis"), "description": v.get("description"), "quote": v.get("quote")})
        for m in re.finditer(r"infra:\s*([^;\n]+)", r.get("summary", "")):
            infra.append({"assessment_id": r["id"], "iteration_id": r.get("iteration_id", ""), "text": m.group(1).strip()})
    result = {"date": now.strftime("%Y-%m-%d"), "assessments": len(rows), "violations": violations, "infra": infra, "open_tasks": open_tasks}
    if a.out:
        write_json(a.out, result)
    out({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()} | {"out": a.out})


def triage_errors(plan, data):
    """Return (errors, actions, journal line) for a triage plan against the triage input."""
    errs, actions = [], []
    ids = {v["assessment_id"] for v in data.get("violations", [])} | {i["assessment_id"] for i in data.get("infra", [])}
    iters = {v["assessment_id"]: v.get("iteration_id") or v.get("task_key") for v in data.get("violations", [])}
    open_keys = {t["key"] for t in data.get("open_tasks", [])}
    date = plan.get("date") or data.get("date", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        errs.append("date must be YYYY-MM-DD")
    causes = plan.get("causes")
    if not isinstance(causes, list):
        return ["causes must be a list"], [], ""
    created, dups, over, noise = [], [], [], []
    new = 0
    for i, c in enumerate(causes):
        name = str(c.get("cause", "")).strip()
        where = f"cause {i} ({name or 'no name'})"
        route, impact = c.get("route"), c.get("impact", "none")
        found = c.get("assessments") or []
        if not name or not re.fullmatch(r"[a-z0-9-]{1,40}", str(c.get("slug", ""))):
            errs.append(f"{where}: needs cause text and slug [a-z0-9-]")
        if route not in TRIAGE_ROUTES:
            errs.append(f"{where}: route must be one of {', '.join(TRIAGE_ROUTES)}")
            continue
        if impact not in TRIAGE_IMPACT:
            errs.append(f"{where}: impact must be one of {', '.join(TRIAGE_IMPACT)}")
        if not found or len(set(found)) != len(found) or not set(found) <= ids:
            errs.append(f"{where}: assessments must be unique IDs from the triage input")
            continue
        count = len(found)
        if route in ("infra", "noise"):
            if c.get("duplicate_of") or c.get("over_limit"):
                errs.append(f"{where}: {route} makes no task, so it has no duplicate_of or over_limit")
            noise.append((name, count))
            continue
        queue, assignee = TRIAGE_QUEUES[route]
        dup = c.get("duplicate_of")
        if dup:
            if dup not in open_keys:
                errs.append(f"{where}: duplicate_of {dup} is not an open task of IMPROVE or TARI")
            dups.append((dup, name, count))
            continue
        if c.get("over_limit"):
            over.append((name, count))
            continue
        new += 1
        wanted = {x for x in (iters.get(f) for f in found) if x}
        if not wanted:
            errs.append(f"{where}: no iteration or task behind the assessments")
        priority = "P1" if count >= 10 or impact == "work_lost" else "P2"
        key = f"triage-{date}-{c.get('slug')}"
        base_args = ["ttasks", "create", "--queue", queue]
        tail_args = ["--priority", priority, "--idempotency-key", key]
        actions.append({"cause": name, "queue": queue, "assignee": assignee, "priority": priority, "count": count,
                        "idempotency_key": key, "assessments": found, "iterations": sorted(wanted),
                        # IMPROVE is bound to a workflow in some deployments: the daemon then assigns the task and
                        # refuses --assignee with workflow_managed. The same command without it is the retry.
                        "create_args": base_args + ["--assignee", assignee] + tail_args,
                        "create_args_unassigned": base_args + tail_args})
    if new > TRIAGE_LIMIT:
        errs.append(f"{new} new tasks; at most {TRIAGE_LIMIT} per day, mark the rest over_limit")
    actions.sort(key=lambda x: (-x["count"], x["cause"]))
    line = (f"Triage {date}: causes {len(causes)}; created "
            + (", ".join(f"KEY_{n} ({x['cause']}, assessments {x['count']})" for n, x in enumerate(actions, 1)) or "none")
            + "; duplicates " + (", ".join(f"{k} ({n}, {m})" for k, n, m in dups) or "none")
            + f"; candidates over limit {len(over)}" + (" (" + "; ".join(f"{n}, {m}" for n, m in over) + ")" if over else "")
            + f"; infra and noise {len(noise)}" + (" (" + "; ".join(f"{n}, {m}" for n, m in noise) + ")" if noise else ""))
    return errs, actions, line


def cmd_triage_check(a):
    errs, actions, line = triage_errors(read_json(a.plan, {}), read_json(a.input, {}))
    out({"ok": not errs, "errors": errs, "create": actions, "journal_line": line})
    if errs:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("cost"); s.add_argument("--agent", required=True); s.add_argument("--since", required=True)
    for name in ("candidates", "coverage"):
        s = sub.add_parser(name)
        if name == "candidates":
            s.add_argument("--dir", required=True)
        for x in ("--agents", "--since", "--assessor"):
            s.add_argument(x, default="")
        s.add_argument("--window", type=int, default=86400, help="seconds; only iterations that ended inside it")
        if name == "candidates":
            s.add_argument("--size", type=int, default=50, help="sample size: at most this many candidates")
            s.add_argument("--reassess", action="store_true",
                           help="also take iterations with only an older rubric assessment of this assessor, at any age")
        s.add_argument("--now", default="", help="RFC 3339 end of the window (tests)")
        s.add_argument("--input", default="", help="gathered iteration rows as JSON instead of the daemon (tests)")
    s = sub.add_parser("pack"); s.add_argument("--dir", required=True); s.add_argument("--limit", type=int, default=10)
    s.add_argument("--window-chars", type=int, default=WINDOW_CHARS, help="characters one assessor subagent reads")
    s = sub.add_parser("tasks"); s.add_argument("--dir", required=True); s.add_argument("--assessor", required=True)
    s.add_argument("--reassess", action="store_true", help="also take done tasks with only an older rubric task assessment")
    s.add_argument("--window-chars", type=int, default=WINDOW_CHARS, help="characters one assessor subagent reads")
    s = sub.add_parser("validate"); s.add_argument("--dir", required=True)
    s = sub.add_parser("add"); s.add_argument("--dir", required=True)
    s.add_argument("--assessor", default=os.environ.get("TARIBOY_AGENT", ""), help="this agent; default $TARIBOY_AGENT")
    s = sub.add_parser("triage-input"); s.add_argument("--assessor", default=os.environ.get("TARIBOY_AGENT", ""))
    s.add_argument("--out", default=""); s.add_argument("--window", type=int, default=86400)
    s.add_argument("--now", default=""); s.add_argument("--input", default="", help="rows as JSON instead of the daemon (tests)")
    s = sub.add_parser("triage-check"); s.add_argument("--plan", required=True); s.add_argument("--input", required=True)
    a = p.parse_args()
    {"cost": cmd_cost, "candidates": cmd_candidates, "coverage": cmd_coverage, "pack": cmd_pack, "tasks": cmd_tasks,
     "validate": cmd_validate, "add": cmd_add, "triage-input": cmd_triage_input,
     "triage-check": cmd_triage_check}[a.cmd](a)


if __name__ == "__main__":
    main()
