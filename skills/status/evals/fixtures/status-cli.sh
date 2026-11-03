#!/usr/bin/env bash
# Fixture for the status skill evals: the skill with a stand-in status CLI.
#
# Usage: status-cli.sh [--message TEXT]
#   --message TEXT   the status message the daemon already holds
#                    (default: empty, as for an agent that never set one)
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/status/SKILL.md            the file of the revision under test
#   $EVAL_DIR/skill/status/scripts/status.sh   the stand-in for the daemon-backed CLI
#   $EVAL_DIR/skill/status/scripts/daemon.py   its daemon, with state in daemon.json
#   $EVAL_DIR/calls.log                        one line per stand-in call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/status and run it in
# $EVAL_DIR. No daemon socket is needed. The stand-in accepts the real CLI's
# arguments (`status.sh`, `status.sh set <message...>`, `--json`, `--help`),
# rejects others, prints in the real CLI's format and keeps the message that
# `set` stores. Grade the actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/status"

message=""
while [ $# -gt 0 ]; do
  case "$1" in
    --message) message=${2?}; shift 2 ;;
    *) echo "usage: status-cli.sh [--message TEXT]" >&2; exit 2 ;;
  esac
done

mkdir -p "$skill/scripts"
cp "$suite_root/SKILL.md" "$skill/"
: > "$EVAL_DIR/calls.log"

cat > "$skill/scripts/status.sh" <<'STATUS_CLI_EOF'
#!/usr/bin/env bash
exec python3 -B "$(dirname "$0")/daemon.py" "$@"
STATUS_CLI_EOF
chmod +x "$skill/scripts/status.sh"

cat > "$skill/scripts/daemon.py" <<'DAEMON_EOF'
import json, shlex, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parents[2]
STATE = HERE / "daemon.json"


def fmt(v):
    if v is None: return "<nil>"
    if isinstance(v, bool): return str(v).lower()
    return str(v)


argv = sys.argv[1:]
if argv[:1] == ["--init"]:
    STATE.write_text(json.dumps({
        "current_iteration": "dev-20260921091500-1", "enabled": True,
        "message": argv[1], "state": "running",
        "updated": "2026-09-21T09:10:00.000000000Z"}))
    sys.exit(0)
with open(EVAL_DIR / "calls.log", "a") as log:
    log.write(" ".join(shlex.quote(a) for a in ["status.sh", *argv]) + "\n")
if argv in (["-h"], ["--help"]):
    print("usage: status.sh [set <message...>] [--json]")
    sys.exit(0)
as_json = "--json" in argv
argv = [a for a in argv if a != "--json"]
for a in argv:
    if a.startswith("--"):
        print(f"unknown flag --{a[2:].split('=', 1)[0]}", file=sys.stderr)
        sys.exit(2)
status = json.loads(STATE.read_text())
if argv[:1] == ["set"]:
    if len(argv) < 2:
        print("tools status set: <message...> required", file=sys.stderr)
        sys.exit(2)
    status.update(message=" ".join(argv[1:]), updated="2026-09-21T09:15:00.000000000Z")
    STATE.write_text(json.dumps(status))
    result = {"message": status["message"], "updated": status["updated"]}
else:
    # like the real CLI, any other positional argument reads the status
    result = status
if as_json:
    print(json.dumps(result, separators=(",", ":")))
else:
    for k in sorted(result): print(f"{k}: {fmt(result[k])}")
DAEMON_EOF
python3 -B "$skill/scripts/daemon.py" --init "$message"
