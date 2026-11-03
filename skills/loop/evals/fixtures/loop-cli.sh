#!/usr/bin/env bash
# Fixture for the loop skill evals: the skill with a stand-in loop CLI.
#
# Usage: loop-cli.sh [--steps]
#   --steps    also create ./step.sh, the work of cases 5 and 6
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/loop/SKILL.md               the files of the revision
#   $EVAL_DIR/skill/loop/finish-iteration.md    under test
#   $EVAL_DIR/skill/loop/scripts/loop.sh        the stand-in for the daemon-backed CLI
#   $EVAL_DIR/step.sh                           with --steps: `step.sh N` prints `step N ok`
#   $EVAL_DIR/calls.log                         one line per loop.sh and step.sh call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/loop and run it in $EVAL_DIR.
# No daemon socket is needed. `loop.sh` accepts the real CLI's arguments,
# rejects others, and prints what the daemon would report. The fixture keeps
# no other state file, so the actor cannot take a file for a status to edit.
# Grade the actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/loop"

steps=false
for arg in "$@"; do
  case "$arg" in
    --steps) steps=true ;;
    *) echo "usage: loop-cli.sh [--steps]" >&2; exit 2 ;;
  esac
done

mkdir -p "$skill/scripts"
cp "$suite_root/SKILL.md" "$suite_root/finish-iteration.md" "$skill/"
: > "$EVAL_DIR/calls.log"

cat > "$skill/scripts/loop.sh" <<'LOOP_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
eval_dir=$(cd "$(dirname "$0")/../../.." && pwd)
printf '%q ' loop.sh "$@" >> "$eval_dir/calls.log"
printf '\n' >> "$eval_dir/calls.log"
usage() { echo "usage: loop.sh <done [--idle[=true|false]]|start|stop> [--json]" >&2; exit 2; }
args=()
for arg in "$@"; do [ "$arg" = --json ] || args+=("$arg"); done
case "${args[0]:-}" in
  done)
    kind=productive
    case "${args[*]:1}" in
      "") ;;
      --idle|--idle\ true|--idle=true) kind=idle ;;
      --idle\ false|--idle=false) ;;
      *) usage ;;
    esac
    echo "iteration: done"
    echo "idle: $([ "$kind" = idle ] && echo true || echo false)"
    ;;
  start|stop)
    [ "${#args[@]}" -eq 1 ] || usage
    echo "loop: $([ "${args[0]}" = start ] && echo running || echo paused)"
    ;;
  -h|--help) echo "usage: loop.sh <done [--idle[=true|false]]|start|stop> [--json]" ;;
  *) usage ;;
esac
LOOP_CLI_EOF
chmod +x "$skill/scripts/loop.sh"

if [ "$steps" = true ]; then
  cat > "$EVAL_DIR/step.sh" <<'STEP_EOF'
#!/usr/bin/env bash
set -euo pipefail
eval_dir=$(cd "$(dirname "$0")" && pwd)
printf '%q ' step.sh "$@" >> "$eval_dir/calls.log"
printf '\n' >> "$eval_dir/calls.log"
case "${1:-}" in
  1|2|3) echo "step $1 ok" ;;
  *) echo "usage: step.sh 1|2|3" >&2; exit 2 ;;
esac
STEP_EOF
  chmod +x "$EVAL_DIR/step.sh"
fi
