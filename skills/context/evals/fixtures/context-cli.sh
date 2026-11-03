#!/usr/bin/env bash
# Fixture for the context skill evals: the skill with a stand-in context CLI.
#
# Usage: context-cli.sh [HANDOFF_LINE...]
#   Each argument is one line of the durable handoff that the run starts with.
#   No argument starts the run with an empty handoff.
#
# The eval runner sets:
#   EVAL_DIR   the case directory; the fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/context/SKILL.md            the SKILL.md of the revision under test
#   $EVAL_DIR/skill/context/scripts/context.sh  the stand-in for the daemon-backed CLI
#   $EVAL_DIR/handoff.txt                       the stored handoff
#   $EVAL_DIR/calls.log                         one line per CLI call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/context. The stand-in needs no
# daemon socket: `get` prints the stored handoff and `set TEXT` replaces it, as
# the real CLI does. Grade the actor on calls.log and the final handoff.txt.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/context"

mkdir -p "$skill/scripts"
cp "$suite_root/SKILL.md" "$skill/SKILL.md"
: > "$EVAL_DIR/calls.log"
if [ "$#" -gt 0 ]; then
  printf '%s\n' "$@" > "$EVAL_DIR/handoff.txt"
else
  : > "$EVAL_DIR/handoff.txt"
fi

cat > "$skill/scripts/context.sh" <<'CONTEXT_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
eval_dir=$(cd "$(dirname "$0")/../../.." && pwd)
printf '%q ' context.sh "$@" >> "$eval_dir/calls.log"
printf '\n' >> "$eval_dir/calls.log"
case "${1:-}" in
  get)
    [ "$#" -eq 1 ] || { echo "usage: context.sh get" >&2; exit 2; }
    cat "$eval_dir/handoff.txt"
    ;;
  set)
    [ "$#" -eq 2 ] || { echo "usage: context.sh set TEXT" >&2; exit 2; }
    printf '%s\n' "$2" > "$eval_dir/handoff.txt"
    echo "context: updated"
    ;;
  *)
    echo "usage: context.sh get | set TEXT" >&2
    exit 2
    ;;
esac
CONTEXT_CLI_EOF
chmod +x "$skill/scripts/context.sh"
