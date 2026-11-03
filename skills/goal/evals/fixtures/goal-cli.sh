#!/usr/bin/env bash
# Fixture for the goal skill evals: the skill with stand-in goal and task CLIs.
#
# Usage: goal-cli.sh [--goal KEY] [TASK_LINE...]
#   --goal KEY   the Goal that the daemon already selected for this agent
#   TASK_LINE    one Native Task as "KEY STATUS ASSIGNEE",
#                for example "TARI-42 in_progress agent:eval-agent"
#
# The eval runner sets:
#   EVAL_DIR   the case directory; the fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/goal/SKILL.md          the SKILL.md of the revision under test
#   $EVAL_DIR/skill/goal/scripts/goal.sh   the stand-in for the daemon-backed CLI
#   $EVAL_DIR/bin/ttasks                   a stand-in task CLI: show KEY, mine
#   $EVAL_DIR/goal.txt                     the selected Goal, empty when none
#   $EVAL_DIR/tasks.txt                    the task lines
#   $EVAL_DIR/calls.log                    one line per CLI call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/goal and put $EVAL_DIR/bin
# first in PATH. The actor is agent:eval-agent. No daemon socket is needed.
# `goal.sh set KEY` follows the SKILL.md contract: it refuses while a Goal is
# selected, and it refuses a task that is not open or in_progress and assigned
# to agent:eval-agent. Grade the actor on calls.log and the final goal.txt.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/goal"

goal=""
if [ "${1:-}" = "--goal" ]; then
  goal=${2:?--goal needs a task key}
  shift 2
fi

mkdir -p "$skill/scripts" "$EVAL_DIR/bin"
cp "$suite_root/SKILL.md" "$skill/SKILL.md"
: > "$EVAL_DIR/calls.log"
printf '%s' "$goal" > "$EVAL_DIR/goal.txt"
if [ "$#" -gt 0 ]; then
  printf '%s\n' "$@" > "$EVAL_DIR/tasks.txt"
else
  : > "$EVAL_DIR/tasks.txt"
fi

cat > "$skill/scripts/goal.sh" <<'GOAL_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
eval_dir=$(cd "$(dirname "$0")/../../.." && pwd)
printf '%q ' goal.sh "$@" >> "$eval_dir/calls.log"
printf '\n' >> "$eval_dir/calls.log"
if [ "$#" -ne 2 ] || [ "$1" != set ]; then
  echo "usage: goal.sh set <task-key> [--json]" >&2
  exit 2
fi
current=$(cat "$eval_dir/goal.txt")
if [ -n "$current" ]; then
  echo "goal already selected: $current" >&2
  exit 1
fi
line=$(awk -v k="$2" '$1 == k' "$eval_dir/tasks.txt")
if [ -z "$line" ]; then
  echo "task not found: $2" >&2
  exit 1
fi
read -r _ status assignee <<< "$line"
case "$status" in open|in_progress) ;; *) assignee="" ;; esac
if [ "$assignee" != agent:eval-agent ]; then
  echo "task $2 must be active and assigned to this agent" >&2
  exit 1
fi
printf '%s' "$2" > "$eval_dir/goal.txt"
echo "key: $2"
echo "selected: true"
GOAL_CLI_EOF

cat > "$EVAL_DIR/bin/ttasks" <<'TASKS_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
eval_dir=$(cd "$(dirname "$0")/.." && pwd)
printf '%q ' ttasks "$@" >> "$eval_dir/calls.log"
printf '\n' >> "$eval_dir/calls.log"
print_task() { printf 'key: %s\nstatus: %s\nassignee: %s\n' "$1" "$2" "$3"; }
case "${1:-}" in
  show)
    [ "$#" -eq 2 ] || { echo "usage: ttasks show <key>" >&2; exit 2; }
    line=$(awk -v k="$2" '$1 == k' "$eval_dir/tasks.txt")
    [ -n "$line" ] || { echo "not_found: $2" >&2; exit 1; }
    print_task $line
    ;;
  mine)
    awk '$3 == "agent:eval-agent" { print $1, $2 }' "$eval_dir/tasks.txt"
    ;;
  *)
    echo "stand-in ttasks supports: show <key>, mine" >&2
    exit 2
    ;;
esac
TASKS_CLI_EOF
chmod +x "$skill/scripts/goal.sh" "$EVAL_DIR/bin/ttasks"
