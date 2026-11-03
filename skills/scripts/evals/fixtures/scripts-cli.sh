#!/usr/bin/env bash
# Fixture for the scripts skill evals: the skill with a stand-in scripts CLI.
#
# Usage: scripts-cli.sh [--state STATE] [--targets] [--task]
#   --state STATE   the definitions the daemon already holds (default: empty)
#                   empty                    no definitions (cases 1, 2)
#                   import-running           active schedule with one running run (case 3)
#                   token-monitor-failed     PR monitor stopped by an exit-1 run (case 4)
#                   pr-monitor-stopped       PR monitor stopped by an exit-0 run (case 5)
#                   release-watch-stopped    release watcher stopped by an exit-0 run (case 6)
#   --targets       also create ./scripts/check-backup.sh and ./scripts/refresh-index.sh
#   --task          also create the task of case 4: a `ttasks` stand-in in ./bin
#                   and a `scripts/loop.sh` stand-in
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/scripts/SKILL.md             the file of the revision under test
#   $EVAL_DIR/skill/scripts/scripts/scripts.sh   the stand-in for the daemon-backed CLI
#   $EVAL_DIR/skill/scripts/scripts/daemon.py    its daemon, with state in daemon.json
#   $EVAL_DIR/scripts/*.sh                       with --targets or --task, see above
#   $EVAL_DIR/bin/ttasks                         with --task; put $EVAL_DIR/bin first on PATH
#   $EVAL_DIR/calls.log                          one line per stand-in call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/scripts and run it in
# $EVAL_DIR. No daemon socket is needed. The stand-in accepts the real CLI's
# arguments, rejects others, resolves only `scr-...` and `srun-...` IDs, prints
# in the real CLI's format, and applies the lifecycle that SKILL.md describes:
# `run` and `schedule` add a definition, `rerun` makes it active, cancelling a
# run publishes its result and stops the definition, `rm` removes it. It
# starts no command. Grade the actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/scripts"

state=empty targets=false task=false
while [ $# -gt 0 ]; do
  case "$1" in
    --state) state=${2:?}; shift 2 ;;
    --targets) targets=true; shift ;;
    --task) task=true; shift ;;
    *) echo "usage: scripts-cli.sh [--state STATE] [--targets] [--task]" >&2; exit 2 ;;
  esac
done
case "$state" in
  empty|import-running|token-monitor-failed|pr-monitor-stopped|release-watch-stopped) ;;
  *) echo "scripts-cli.sh: unknown state $state" >&2; exit 2 ;;
esac

mkdir -p "$skill/scripts"
cp "$suite_root/SKILL.md" "$skill/"
: > "$EVAL_DIR/calls.log"

cat > "$skill/scripts/scripts.sh" <<'SCRIPTS_CLI_EOF'
#!/usr/bin/env bash
exec python3 -B "$(dirname "$0")/daemon.py" "$@"
SCRIPTS_CLI_EOF
chmod +x "$skill/scripts/scripts.sh"

cat > "$skill/scripts/daemon.py" <<'DAEMON_EOF'
import json, shlex, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parents[2]
STATE = HERE / "daemon.json"
P, R = "scr-dev-20260921061500-", "srun-dev-20260921061500-"
LOGS = "/home/agent/.tariboy/agents/dev/scripts/"


def definition(n, name, command, every, run_n, status, exit_code, state):
    run = {"agent": "dev", "created_at": "2026-09-21T09:15:00Z", "id": f"{R}{run_n:09d}",
           "log_path": f"{LOGS}{R}{run_n:09d}.log", "script_id": f"{P}{n:09d}",
           "started_at": "2026-09-21T09:15:00Z", "status": status}
    if exit_code is not None:
        run.update(exit_code=exit_code, finished_at="2026-09-21T09:15:03Z")
    return {"agent": "dev", "command": command, "created_at": "2026-09-21T06:15:00Z",
            "description": name, "id": f"{P}{n:09d}", "interval_seconds": every,
            "latest_run": run, "mode": "every", "name": name,
            "next_run_at": None, "state": state}


MONITOR = "/home/agent/skills/github-pr-workflow/scripts/github-pr.py monitor --repo acme/widget"
STATES = {
    "empty": [],
    "import-running": [definition(1, "nightly-import", "./scripts/import.sh", 3600, 5, "running", None, "active")],
    "token-monitor-failed": [definition(2, "pr-17-closure", MONITOR + " --pr 17 --state-dir /home/agent/workdir/pr-monitor/TASK-17", 60, 7, "failed", 1, "completed")],
    "pr-monitor-stopped": [definition(3, "pr-monitor-dev-42", MONITOR + " --pr 42 --state-dir /home/agent/workdir/pr-monitor/TASK-42", 60, 9, "succeeded", 0, "completed")],
    "release-watch-stopped": [definition(4, "release-watch-dev-42", "./scripts/release-watch.sh", 300, 11, "succeeded", 0, "completed")],
}


def fmt(v):
    if v is None: return "<nil>"
    if isinstance(v, bool): return str(v).lower()
    if isinstance(v, list): return "[" + " ".join(fmt(i) for i in v) + "]"
    if isinstance(v, dict): return "map[" + " ".join(f"{k}:{fmt(v[k])}" for k in sorted(v)) + "]"
    return str(v)


def show(result):
    if JSON: print(json.dumps(result, separators=(",", ":"))); return
    for k in sorted(result): print(f"{k}: {fmt(result[k])}")


class Usage(Exception): pass
class Failure(Exception): pass


def find(defs, ident):
    for d in defs:
        if d["id"] == ident or d["latest_run"]["id"] == ident:
            return d
    raise Failure(f"script {ident} not found")


def create(defs, args, scheduled):
    action = "schedule" if scheduled else "run"
    if len(args) < 3 or "--" not in args[2:]:
        raise Usage(f"tools script {action}: NAME [options] -- COMMAND required")
    sep = args.index("--", 2)
    flags, i = {}, 2
    allowed = {"description", "every"} if scheduled else {"description"}
    while i < sep:
        a = args[i]
        if not a.startswith("--"):
            raise Usage(f'tools script {action}: unexpected argument "{a}" before --')
        name, eq, val = a[2:].partition("=")
        if scheduled and name == "quiet-exit":
            raise Usage("tools script schedule: --quiet-exit is not supported; a recurring command exits with $TARIBOY_QUIET_EXIT (111) to stay quiet")
        if name not in allowed:
            raise Usage(f"unknown flag --{name}")
        if not eq:
            i += 1
            val = args[i] if i < sep else "true"
        flags[name] = val
        i += 1
    command = " ".join(args[sep + 1:])
    if not command.strip():
        raise Usage(f"tools script {action}: command is required after --")
    n = max([19] + [int(x["id"][len(P):]) for x in defs]) + 1
    d = definition(n, args[1], command, None, n + 20, "running", None, "active")
    d["description"] = flags.get("description", args[1])
    if scheduled:
        every = flags.get("every", "")
        if not every.isdigit() or int(every) <= 0:
            raise Usage("tools script schedule: --every must be a positive number of seconds")
        d["interval_seconds"] = int(every)
    else:
        d["mode"] = "once"
    defs.append(d)
    return d


def main(args):
    defs = json.loads(STATE.read_text())
    cmd = args[0] if args else ""
    if args in (["-h"], ["--help"]):
        print("usage: scripts.sh <run|schedule|ls|runs|logs|rerun|cancel|rm> ... [--json]"); return
    if cmd in ("run", "schedule"):
        show(create(defs, args, cmd == "schedule"))
    elif args == ["ls"]:
        show({"count": len(defs), "scripts": defs})
    elif cmd in ("runs", "logs", "rerun", "cancel", "rm"):
        ids = [a for a in args[1:] if not a.startswith("--")]
        if not ids:
            raise Usage(f"tools script {cmd}: <id> is required")
        d = find(defs, ids[0])
        if cmd == "runs":
            show({"count": 1, "runs": [d["latest_run"]]})
        elif cmd == "logs":
            print("(empty log)")
        elif cmd == "rerun":
            if d["state"] == "cancelled":
                raise Failure(f"script {d['id']} is cancelled")
            d["state"] = "active"
            run = {k: v for k, v in d["latest_run"].items() if k not in ("exit_code", "finished_at")}
            d["latest_run"] = dict(run, status="running")
            show(d)
        elif cmd == "cancel":
            if ids[0].startswith(R):
                if d["latest_run"]["status"] != "running":
                    raise Failure(f"run {ids[0]} is not running")
                d["latest_run"] = dict(d["latest_run"], status="cancelled", exit_code=-1, finished_at="2026-09-21T09:15:30Z")
                d["state"] = "completed"
                show(d["latest_run"])
            else:
                d["state"] = "cancelled"
                show(d)
        else:
            defs.remove(d)
            show({"id": d["id"], "removed": True})
    else:
        raise Usage("tools script: unknown command " + " ".join(args))
    STATE.write_text(json.dumps(defs))


argv = sys.argv[1:]
if argv[:1] == ["--init"]:
    STATE.write_text(json.dumps(STATES[argv[1]]))
    sys.exit(0)
with open(EVAL_DIR / "calls.log", "a") as log:
    log.write(" ".join(shlex.quote(a) for a in ["scripts.sh", *argv]) + "\n")
JSON = "--json" in argv
argv = [a for a in argv if a != "--json"]
try:
    main(argv)
except Usage as e:
    print(e, file=sys.stderr); sys.exit(2)
except Failure as e:
    print(e, file=sys.stderr); sys.exit(1)
DAEMON_EOF
python3 -B "$skill/scripts/daemon.py" --init "$state"

record() {
  # $1 file, $2 logged name, $3 body; the body runs after the call is logged
  cat > "$1" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%q ' $2 "\$@" >> "$EVAL_DIR/calls.log"
printf '\n' >> "$EVAL_DIR/calls.log"
$3
EOF
  chmod +x "$1"
}

if [ "$targets" = true ] || [ "$task" = true ]; then mkdir -p "$EVAL_DIR/scripts"; fi
if [ "$targets" = true ]; then
  record "$EVAL_DIR/scripts/check-backup.sh" check-backup.sh 'echo "backup ok"'
  record "$EVAL_DIR/scripts/refresh-index.sh" refresh-index.sh 'echo "index refreshed"'
fi

if [ "$task" = true ]; then
  mkdir -p "$EVAL_DIR/bin"
  record "$EVAL_DIR/scripts/loop.sh" loop.sh 'case "${1:-}" in
  done) echo "iteration: done" ;;
  *) echo "usage: loop.sh <done [--idle]|start|stop>" >&2; exit 2 ;;
esac'
  record "$EVAL_DIR/bin/ttasks" ttasks 'case "${1:-}" in
  mine) echo "TASK-17  wait_customer  Fix the widget export  customer:user:alice" ;;
  show)
    [ "${2:-}" = TASK-17 ] || { echo "not found: ${2:-}" >&2; exit 1; }
    cat <<TASK_EOF
task: TASK-17 Fix the widget export
status: wait_customer
customer: user:alice
pull_request: https://github.com/acme/widget/pull/17
monitor: pr-17-closure
questions:
- id 514, to user:alice, unanswered: "@alice The PR monitor fails because GH_TOKEN or GITHUB_TOKEN is missing in this environment. Please provide a GitHub token through the agent secret store."
comments: 20 comments "PR monitor failed: GH_TOKEN or GITHUB_TOKEN is not set" by agent:dev
TASK_EOF
    ;;
  comment|ask|update) [ "${2:-}" = TASK-17 ] || { echo "not found: ${2:-}" >&2; exit 1; }; echo "ok" ;;
  *) echo "usage: ttasks <mine|show|comment|ask|update> ..." >&2; exit 2 ;;
esac'
fi
