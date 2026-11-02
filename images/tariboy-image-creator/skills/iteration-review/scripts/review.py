#!/usr/bin/env python3
"""Review cycle helper for the iteration-review skill.

Subcommands (all JSON on stdout, diagnostics on stderr):
  tick       --state FILE [--period SECONDS]     schedule body: quiet (111) until a period passed
  cost       --agent NAME --since TIME            total cost of the cycle so far
  candidates --dir DIR --agents A,B --since TIME --assessor NAME [--window S] [--target N]
             the cycle's selection: last 24 h, a quota per agent x image version, problems first inside it
  coverage   --agents A,B --since TIME --assessor NAME [--window S] [--target N]
             metric 1: active pairs agent x image version and pairs with enough assessments
  pack       --dir DIR [--limit N]                evidence packs for the next N candidates
  tasks      --dir DIR --assessor NAME            done tasks that are ready for a task assessment
  validate   --dir DIR                            check every DIR/out/*.json before it is written
  add        --dir DIR                            write every valid, not yet written assessment

Only `add` writes to the daemon (`tariboy assessment add`). Everything else reads.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RUBRIC = "iteration-review/1"
AXES = ("image_process", "role", "task_fit")
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9a-z]{4}\b|\b[A-Z][A-Z0-9]*-[0-9]+\b")
INFRA_CODES = {137}  # 143 (SIGTERM) is the normal end after `loop.sh done`
PACK_TRANSCRIPT_CHARS = 24000


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


# ---------------------------------------------------------------- tick / cost

def cmd_tick(a):
    state = Path(a.state)
    last = read_json(state, {}).get("last_wake", 0)
    now = time.time()
    if now - last < a.period:
        sys.exit(int(os.environ.get("TARIBOY_QUIET_EXIT", "111")))
    write_json(state, {"last_wake": now})
    out({"review_cycle": "due", "at": dt.datetime.now(dt.timezone.utc).isoformat()})


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
    """True when the assessor already wrote an assessment of this iteration, or of this whole task."""
    args = ["assessment", "ls", "--assessor", assessor, "--limit", "1000"]
    args += ["--iteration", iteration] if iteration else ["--task", task]
    rows = (tb(*args) or {}).get("assessments") or []
    if iteration:
        return bool(rows)
    return any(not r.get("iteration_id") for r in rows)


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


def select(rows, now, window, target):
    """Pick the cycle's candidates from gathered iteration rows.

    Each row: agent, id, status, productive, ended_at, image_version, assessed, marks.
    1. Only iterations finished in the last `window` seconds; older unassessed ones are skipped.
    2. Each pair agent x image_version has a quota of `target` assessments, assessed ones included;
       a pair with fewer iterations gets all of them.
    3. Inside the quota of a pair: problem iterations first, then the rest, newest first.
       Problem iterations over the quota are not selected.
    4. Output order: the problem picks of all pairs newest first, then the other picks round by round
       over the pairs, so a budget stop leaves the pairs even.
    An already assessed iteration is never a candidate.
    """
    start = now - dt.timedelta(seconds=window)
    skipped = {"running": 0, "assessed": 0, "older_than_window": 0, "not_selected": 0, "problem_over_quota": 0}
    pairs = {}
    for r in rows:
        if r.get("status") == "running":
            skipped["running"] += 1
            continue
        ended = parse_time(r.get("ended_at")) or parse_time(r.get("started_at"))
        if ended is None or ended < start or ended > now:
            if not r.get("assessed"):
                skipped["older_than_window"] += 1
            continue
        r = dict(r, _ended=ended, problems=problems_of(r))
        pair = (r["agent"], r.get("image_version") or "")
        st = pairs.setdefault(pair, {"total": 0, "assessed": 0, "open": []})
        st["total"] += 1
        if r.get("assessed"):
            skipped["assessed"] += 1
            st["assessed"] += 1
            continue
        st["open"].append(r)
    newest = lambda r: (r["_ended"], r["id"])
    problem, rest = [], {}
    for pair, st in pairs.items():
        ordered = sorted((r for r in st["open"] if r["problems"]), key=newest, reverse=True)
        ordered += sorted((r for r in st["open"] if not r["problems"]), key=newest, reverse=True)
        chosen = ordered[:max(0, target - st["assessed"])]
        st["chosen"] = len(chosen)
        skipped["not_selected"] += len(ordered) - len(chosen)
        skipped["problem_over_quota"] += sum(1 for r in ordered[len(chosen):] if r["problems"])
        problem += [r for r in chosen if r["problems"]]
        rest[pair] = [r for r in chosen if not r["problems"]]
    problem.sort(key=newest, reverse=True)
    sample, rnd = [], 0
    while any(rnd < len(v) for v in rest.values()):
        for pair in sorted(rest):
            if rnd < len(rest[pair]):
                sample.append(dict(rest[pair][rnd], reason="pair_sample"))
        rnd += 1
    picked = [dict(r, reason="problem") for r in problem] + sample
    out_rows = [{k: v for k, v in r.items() if not k.startswith("_") and k != "assessed"} for r in picked]
    pair_rows = [{"agent": a, "image_version": v, "iterations": st["total"], "assessed": st["assessed"],
                  "planned": st["chosen"]} for (a, v), st in sorted(pairs.items())]
    return out_rows, skipped, pair_rows, {"from": iso(start), "to": iso(now)}


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
            if agent == assessor and 'Script "review-cycle"' in prompt:
                continue  # the cycle's own iterations are not assessed
            row["task_key"], row["task_source"] = task_key_of(prompt)
            if marks and not row["assessed"]:
                row["marks"] = transcript_problems(agent, it["id"])
            rows.append(row)
    return rows


def now_arg(a):
    return parse_time(a.now) if getattr(a, "now", None) else dt.datetime.now(dt.timezone.utc)


def cmd_candidates(a):
    d = Path(a.dir)
    now = now_arg(a)
    rows = read_json(a.input, []) if a.input else gather(a.agents, a.since, a.assessor, now, a.window)
    picked, skipped, pairs, window = select(rows, now, a.window, a.target)
    write_json(d / "candidates.json", picked)
    write_json(d / "pairs.json", pairs)
    out({"window": window, "candidates": len(picked),
         "problem": sum(r["reason"] == "problem" for r in picked), "skipped": skipped,
         "active_pairs": len(pairs), "file": str(d / "candidates.json")})


def coverage(rows, now, window, target):
    start = now - dt.timedelta(seconds=window)
    pairs = {}
    for r in rows:
        if r.get("status") == "running":
            continue
        ended = parse_time(r.get("ended_at")) or parse_time(r.get("started_at"))
        if ended is None or ended < start or ended > now:
            continue
        st = pairs.setdefault((r["agent"], r.get("image_version") or ""), {"total": 0, "assessed": 0})
        st["total"] += 1
        st["assessed"] += bool(r.get("assessed"))
    covered = [p for p, st in pairs.items() if st["assessed"] >= min(target, st["total"])]
    return {"window": {"from": iso(start), "to": iso(now)}, "active_pairs": len(pairs), "covered_pairs": len(covered),
            "share": round(len(covered) / len(pairs), 4) if pairs else None,
            "assessed_iterations": sum(st["assessed"] for st in pairs.values()),
            "pairs": [{"agent": a, "image_version": v, **st, "covered": (a, v) in covered}
                      for (a, v), st in sorted(pairs.items())]}


def cmd_coverage(a):
    now = now_arg(a)
    rows = read_json(a.input, []) if a.input else gather(a.agents, a.since, a.assessor, now, a.window, marks=False)
    out(coverage(rows, now, a.window, a.target))


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


def transcript_lines(agent, iteration):
    data = tb("transcript", agent, iteration, check=False) or {}
    lines = []
    for call in data.get("calls") or []:
        seq = call.get("seq")
        if call.get("status") not in ("ok", None):
            if call.get("status") != "quota_probe":
                lines.append(f"[seq {seq}] API status {call.get('status')}")
        for msg in call.get("delta") or []:
            for b in msg.get("blocks") or []:
                if msg.get("role") == "user" and b.get("type") == "tool_result":
                    lines.append(f"[seq {seq}] result: {clip(b.get('text'), 300)}")
                elif (msg.get("role") == "user" and b.get("type") == "text" and seq and seq > 3
                      and not (b.get("text") or "").lstrip().startswith(("<system-reminder>", "Base directory for this skill"))):
                    lines.append(f"[seq {seq}] user: {clip(b.get('text'), 200)}")
        for b in (call.get("response") or {}).get("blocks") or []:
            if b.get("type") == "tool_use":
                lines.append(f"[seq {seq}] call {b.get('tool_name')}: {clip(json.dumps(b.get('input'), ensure_ascii=False), 400)}")
            elif b.get("type") == "text":
                lines.append(f"[seq {seq}] text: {clip(b.get('text'), 300)}")
    body = "\n".join(lines)
    if len(body) > PACK_TRANSCRIPT_CHARS:
        half = PACK_TRANSCRIPT_CHARS // 2
        body = body[:half] + "\n…[middle of transcript clipped]…\n" + body[-half:]
    return body


def task_block(key, agent):
    if not key:
        return "No task: the iteration had no goal task and no letter named one.\n"
    show = tb("tasks", "show", key, check=False)
    if not show:
        return f"Task {key}: not readable.\n"
    t = show.get("task", show)
    parts = [f"key: {key}", f"title: {t.get('title', '')}", f"status: {t.get('status', '')}",
             f"assignee: {t.get('assignee', '')}", f"created_at: {t.get('created_at', '')}",
             f"workflow: {t.get('workflow', '') or t.get('workflow_ref', '') or 'none'}",
             "description:", clip(t.get("description", ""), 1500), "", "comments (latest 8):"]
    for c in (show.get("comments") or [])[-8:]:
        parts.append(f"- comment {c.get('id')} by {c.get('author')} at {c.get('created_at')}: {clip(c.get('body'), 600)}")
    ev = tb("tasks", "events", "--key", key, check=False) or {}
    parts.append("")
    parts.append("events (sequence kind actor payload):")
    for e in (ev.get("events") or [])[-40:]:
        parts.append(f"- {e.get('sequence')} {e.get('kind')} {e.get('actor')} {clip(json.dumps(e.get('payload'), ensure_ascii=False), 160)}")
    return "\n".join(parts) + "\n"


def cmd_pack(a):
    d = Path(a.dir)
    cands = read_json(d / "candidates.json", [])
    packed = []
    for c in cands:
        if len(packed) >= a.limit:
            break
        p = d / "packs" / f"{c['id']}.md"
        if p.exists() or (d / "out" / f"{c['id']}.json").exists():
            continue
        info = tb("iteration", "inspect", c["agent"], c["id"], check=False) or {}
        info = info.get("iteration", info)
        res = read_json(Path(info.get("prompt_path", "/nonexistent")).parent / "result.json", {})
        prompt = ""
        try:
            prompt = Path(info.get("prompt_path", "")).read_text()
        except OSError:
            prompt = ""
        secs = prompt_sections(prompt)
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
        text = "\n".join([
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
            clip(order, 6000),
            "",
            "## ROLE.md",
            f"source: {role_src}",
            role if role else "ABSENT: the axis `role` is `not_applicable`.",
            "",
            "## Image instructions of this version",
            clip(instr, 16000),
            "",
            "## User prompt",
            clip(user, 3000) or "none",
            "",
            "## Transcript (locator = seq N)",
            transcript_lines(c["agent"], c["id"]),
        ])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n")
        packed.append({"id": c["id"], "agent": c["agent"], "task_key": c.get("task_key", ""), "pack": str(p),
                       "out": str(d / "out" / f"{c['id']}.json")})
    remaining = sum(1 for c in cands if not (d / "packs" / f"{c['id']}.md").exists())
    write_json(d / "batch.json", packed)
    out({"packed": packed, "remaining_unpacked": remaining})


# ---------------------------------------------------------------- tasks

def cmd_tasks(a):
    d = Path(a.dir)
    cands = read_json(d / "candidates.json", [])
    added = {r["file"] for r in read_json(d / "added.json", [])}
    open_iters = {}
    for c in cands:
        if c.get("task_key") and str(d / "out" / f"{c['id']}.json") not in added:
            open_iters.setdefault(c["task_key"], []).append(c["id"])
    ready = []
    for key in sorted({c["task_key"] for c in cands if c.get("task_key")}):
        if open_iters.get(key) or has_assessment(a.assessor, task=key):
            continue
        show = tb("tasks", "show", key, check=False)
        t = (show or {}).get("task", show or {})
        if t.get("status") != "done":
            continue
        rows = (tb("assessment", "ls", "--task", key, "--limit", "1000", check=False) or {}).get("assessments") or []
        ev = (tb("tasks", "events", "--key", key, check=False) or {}).get("events") or []
        kinds = [e.get("kind", "") for e in ev]
        payloads = [json.dumps(e.get("payload"), ensure_ascii=False) for e in ev]
        p = d / "packs" / f"task-{key}.md"
        lines = [f"# Task pack {key}", "", "Assess the whole task: write `task_key`, no `iteration_id`.", "",
                 "## Task", task_block(key, ""), "## Measures",
                 f"created_at: {t.get('created_at')}  done_at: {t.get('updated_at')}",
                 f"rework rounds (changes_requested or reopened): {sum(('changes_requested' in x) or ('reopen' in x) for x in kinds + payloads)}",
                 f"questions to the customer (task.question_asked or waits): {sum(('question' in k) or ('wait' in k) for k in kinds)}",
                 "", "## Iteration assessments of this task"]
        for r in rows:
            lines.append(f"- {r.get('id')} iteration {r.get('iteration_id') or '-'}: {clip(r.get('summary'), 300)}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n")
        ready.append({"task_key": key, "pack": str(p), "out": str(d / "out" / f"task-{key}.json")})
    write_json(d / "task-batch.json", ready)
    out({"task_packs": ready})


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
    for i, v in enumerate(obj.get("violations") or []):
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


def cmd_validate(a):
    d = Path(a.dir)
    report = []
    for f in sorted((d / "out").glob("*.json")):
        try:
            obj = json.loads(f.read_text())
            errs = check(obj)
        except json.JSONDecodeError as e:
            errs = [f"not JSON: {e}"]
        report.append({"file": str(f), "ok": not errs, "errors": errs})
    write_json(d / "validate.json", report)
    out({"valid": sum(r["ok"] for r in report), "invalid": [r for r in report if not r["ok"]]})
    if any(not r["ok"] for r in report):
        sys.exit(1)


def cmd_add(a):
    d = Path(a.dir)
    added = read_json(d / "added.json", [])
    done = {r["file"] for r in added}
    results = []
    for f in sorted((d / "out").glob("*.json")):
        if str(f) in done:
            continue
        obj = json.loads(f.read_text())
        if check(obj):
            results.append({"file": str(f), "error": "invalid, run validate"})
            continue
        proc = subprocess.run(["tariboy", "assessment", "add", "--file", str(f), "--json"], capture_output=True, text=True)
        note = ""
        if proc.returncode != 0 and obj.get("iteration_id") and obj.get("task_key") and "link" in (proc.stderr + proc.stdout).lower():
            obj.pop("task_key")
            alt = f.with_suffix(".nolink.json")
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
    out({"written": [r for r in results if "id" in r], "failed": [r for r in results if "error" in r],
         "total_written_this_cycle": len(added)})
    if any("error" in r for r in results):
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("tick"); s.add_argument("--state", required=True); s.add_argument("--period", type=int, default=86400)
    s = sub.add_parser("cost"); s.add_argument("--agent", required=True); s.add_argument("--since", required=True)
    for name in ("candidates", "coverage"):
        s = sub.add_parser(name)
        if name == "candidates":
            s.add_argument("--dir", required=True)
        for x in ("--agents", "--since", "--assessor"):
            s.add_argument(x, default="")
        s.add_argument("--window", type=int, default=86400, help="seconds; only iterations that ended inside it")
        s.add_argument("--target", type=int, default=3, help="assessments per pair agent x image_version")
        s.add_argument("--now", default="", help="RFC 3339 end of the window (tests)")
        s.add_argument("--input", default="", help="gathered iteration rows as JSON instead of the daemon (tests)")
    s = sub.add_parser("pack"); s.add_argument("--dir", required=True); s.add_argument("--limit", type=int, default=10)
    s = sub.add_parser("tasks"); s.add_argument("--dir", required=True); s.add_argument("--assessor", required=True)
    s = sub.add_parser("validate"); s.add_argument("--dir", required=True)
    s = sub.add_parser("add"); s.add_argument("--dir", required=True)
    a = p.parse_args()
    {"tick": cmd_tick, "cost": cmd_cost, "candidates": cmd_candidates, "coverage": cmd_coverage, "pack": cmd_pack, "tasks": cmd_tasks,
     "validate": cmd_validate, "add": cmd_add}[a.cmd](a)


if __name__ == "__main__":
    main()
