#!/usr/bin/env bash
# Fixture for the tasks skill evals: the skill with stand-in ttasks and tmail.
#
# Usage: tasks-cli.sh [--task KEY:STATUS]... [--workflow-task KEY:STATUS:HOLDER]...
#                     [--file NAME=TEXT]... [--store]
#   --task KEY:STATUS                   a flexible task in STATUS
#   --workflow-task KEY:STATUS:HOLDER   a workflow task in STATUS; HOLDER is
#                                       agent (the actor holds the status),
#                                       customer or script
#   --file NAME=TEXT                    a file NAME in $EVAL_DIR with TEXT and a
#                                       final newline, for a file the case prompt names
#   --store                             also derive the Store layout of the
#                                       revision under test into $EVAL_DIR/store
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/tasks/          SKILL.md and scripts/ of the revision under test
#   $EVAL_DIR/bin/ttasks, tasks     the stand-in Native Tasks CLI
#   $EVAL_DIR/bin/tmail             the stand-in mail CLI
#   $EVAL_DIR/bin/state.json        the stand-in task state
#   $EVAL_DIR/NAME                  with --file: the named file
#   $EVAL_DIR/calls.log             one JSON argv line per stand-in call, in order
#   $EVAL_DIR/store/                with --store: images/*/Tariboyfile.yaml,
#                                   images/*/skills-lock.json and the skills/ names
#
# Put $EVAL_DIR/bin first on PATH, give the actor the skill from
# $EVAL_DIR/skill/tasks and run it in $EVAL_DIR. No daemon socket is needed and
# no live task changes. The stand-in keeps task status, assignee, comments and
# artifacts; it refuses `done` and `update --status` on a workflow task
# (workflow_managed), `advance` from a status the actor does not hold
# (not_holder), and every write to a workflow task that a script holds
# (not_found). Grade the actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
store_root=$(cd "$suite_root/../.." && pwd)

tasks_json="{}"
store=0
add_task() {
  tasks_json=$(python3 -c 'import json,sys
t=json.loads(sys.argv[1]); p=sys.argv[3].split(":")
if sys.argv[2]=="flexible" and len(p)==2: t[p[0]]={"status":p[1],"workflow":False,"holder":"agent"}
elif sys.argv[2]=="workflow" and len(p)==3 and p[2] in ("agent","customer","script"): t[p[0]]={"status":p[1],"workflow":True,"holder":p[2]}
else: sys.exit("bad task value: "+sys.argv[3])
print(json.dumps(t))' "$tasks_json" "$1" "$2")
}
usage() { echo "usage: tasks-cli.sh [--task KEY:STATUS]... [--workflow-task KEY:STATUS:HOLDER]... [--file NAME=TEXT]... [--store]" >&2; exit 2; }
files=()
while [ $# -gt 0 ]; do
  case "$1" in
    --task) add_task flexible "${2?}"; shift 2 ;;
    --workflow-task) add_task workflow "${2?}"; shift 2 ;;
    --file) files+=("${2?}"); shift 2 ;;
    --store) store=1; shift ;;
    *) usage ;;
  esac
done

mkdir -p "$EVAL_DIR/skill/tasks" "$EVAL_DIR/bin"
cp "$suite_root/SKILL.md" "$EVAL_DIR/skill/tasks/"
cp -r "$suite_root/scripts" "$EVAL_DIR/skill/tasks/"
: > "$EVAL_DIR/calls.log"
for spec in ${files[@]+"${files[@]}"}; do
  name=${spec%%=*}
  case "$name" in ""|/*|*..*|"$spec") echo "bad file value: $spec" >&2; exit 2 ;; esac
  mkdir -p "$(dirname "$EVAL_DIR/$name")"
  printf '%s\n' "${spec#*=}" > "$EVAL_DIR/$name"
done
printf '%s\n' "$tasks_json" | python3 -c 'import json,sys; json.dump({"tasks":json.load(sys.stdin),"next":43,"comment":400},open(sys.argv[1],"w"))' "$EVAL_DIR/bin/state.json"

if [ "$store" = 1 ]; then
  for dir in "$store_root"/images/*/; do
    name=$(basename "$dir")
    mkdir -p "$EVAL_DIR/store/images/$name"
    for f in Tariboyfile.yaml skills-lock.json; do
      [ -f "$dir$f" ] && cp "$dir$f" "$EVAL_DIR/store/images/$name/"
    done
  done
  for dir in "$store_root"/skills/*/; do mkdir -p "$EVAL_DIR/store/skills/$(basename "$dir")"; done
fi

for cli in ttasks tasks tmail; do
  printf '#!/usr/bin/env bash\nexec python3 -B "$(dirname "$0")/stand-in.py" %s "$@"\n' "$cli" > "$EVAL_DIR/bin/$cli"
  chmod +x "$EVAL_DIR/bin/$cli"
done

cat > "$EVAL_DIR/bin/stand-in.py" <<'STAND_IN_EOF'
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
LOG = HERE.parent / "calls.log"

cli, args = sys.argv[1], sys.argv[2:]
if cli == "tasks":
    cli = "ttasks"
with LOG.open("a") as f:
    f.write(json.dumps([cli] + args, ensure_ascii=False) + "\n")
state = json.loads(STATE.read_text())
tasks = state["tasks"]


def save():
    STATE.write_text(json.dumps(state))


def fail(code, msg):
    print(f"error ({code}): {msg}", file=sys.stderr)
    sys.exit(1)


def flag(name):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else ""
    return None


if cli == "tmail":
    if not args or args[0] in ("-h", "--help"):
        print("Usage: tmail <inbox|show|send|reply|ack> [args]")
    elif args[0] == "reply" and len(args) >= 3:
        print(f"replied to {args[1]}")
    elif args[0] in ("inbox", "show", "send", "ack"):
        print("ok")
    else:
        fail("usage", "tmail reply ID TEXT")
    sys.exit(0)

if not args or "--help" in args or "-h" in args:
    print("Usage: ttasks <command> [args] [flags]\n\nCommands: advance artifacts ask assign comment create done list mine ready show update workflow")
    sys.exit(0)

cmd, rest = args[0], args[1:]


def task(key, write=True):
    t = tasks.get(key)
    if t is None or (write and t["workflow"] and t["holder"] == "script"):
        fail("not_found", f'task "{key}" not found')
    return t


if cmd in ("mine", "list"):
    for k, t in tasks.items():
        print(f'{k}\t{t["status"]}')
elif cmd == "ready":
    ready = [k for k, t in tasks.items() if not t["workflow"] and t["status"] == "open"]
    if "--claim" in rest:
        if not ready:
            print("no ready task")
        else:
            tasks[ready[0]]["status"] = "in_progress"
            save()
            print(f"claimed {ready[0]}")
    else:
        for k in ready:
            print(k)
elif cmd == "show":
    key = rest[0] if rest else ""
    t = task(key, write=False)
    print(f'key: {key}\nstatus: {t["status"]}\nworkflow: {str(t["workflow"]).lower()}')
    for c in t.get("comments", []):
        print(f"comment {c[0]}: {c[1]}")
    for a in t.get("artifacts", {}):
        print(f"artifact: {a}")
elif cmd == "create":
    key = f'TASK-{state["next"]}'
    state["next"] += 1
    tasks[key] = {"status": "open", "workflow": False, "holder": "agent"}
    parent = flag("--parent")
    if parent:
        task(parent)
    save()
    print(key)
elif cmd in ("comment", "ask"):
    key = rest[0] if rest else ""
    t = task(key)
    if len(rest) < (3 if cmd == "ask" else 2):
        fail("usage", f"ttasks {cmd} KEY {'PRINCIPAL ' if cmd == 'ask' else ''}TEXT")
    state["comment"] += 1
    t.setdefault("comments", []).append([state["comment"], rest[-1]])
    save()
    print(f'{cmd} {state["comment"]} added to {key}')
elif cmd == "assign":
    key = rest[0] if rest else ""
    t = task(key)
    if t["workflow"]:
        fail("workflow_managed", "the workflow assigns this task")
    if len(rest) < 2 or ":" in rest[1]:
        fail("usage", "ttasks assign KEY AGENT_NAME")
    t["assignee"] = rest[1]
    save()
    print(f"assigned {key} to {rest[1]}")
elif cmd in ("update", "done"):
    key = rest[0] if rest else ""
    t = task(key)
    status = flag("--status") if cmd == "update" else "done"
    if t["workflow"] and status:
        fail("workflow_managed", "use ttasks advance on a workflow task")
    if status:
        t["status"] = status
    save()
    print(f'{key} status: {t["status"]}')
elif cmd == "advance":
    key = rest[0] if rest else ""
    t = task(key)
    if not t["workflow"]:
        fail("usage", "advance is for workflow tasks")
    if t["holder"] != "agent":
        fail("not_holder", f'status "{t["status"]}" is held by {t["holder"]}')
    if flag("--outcome") is None or flag("--from") != t["status"]:
        fail("usage", "ttasks advance KEY --outcome NAME --from CURRENT_STATUS")
    t["holder"] = "script"
    save()
    print(f'{key} advanced with outcome {flag("--outcome")}')
elif cmd == "artifacts" and rest and rest[0] == "set":
    if len(rest) < 3:
        fail("usage", "ttasks artifacts set KEY NAME [VALUE|--file PATH]")
    t = task(rest[1])
    t.setdefault("artifacts", {})[rest[2]] = True
    save()
    print(f"artifact {rest[2]} set on {rest[1]}")
elif cmd in ("artifacts", "workflow"):
    key = rest[1] if len(rest) > 1 else ""
    t = task(key, write=False)
    print(f'key: {key}\nstatus: {t["status"]}')
else:
    fail("usage", f"unknown command {cmd}")
STAND_IN_EOF
