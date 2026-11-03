#!/usr/bin/env bash
# Fixture for the mail skill evals: the skill with stand-in tmail and ttasks.
#
# Usage: mail-cli.sh [--open ID]... [--dead-letter] [--manifest]
#   --open ID       a letter of the case prompt; `tmail inbox` lists it and
#                   `tmail reply` and `tmail show` accept it
#   --dead-letter   `tmail archive` lists one dead letter that `tmail requeue`
#                   accepts
#   --manifest      copy images/basic/Tariboyfile.yaml and skills-lock.json of
#                   the revision under test to $EVAL_DIR/images/basic/
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/mail/SKILL.md          the files of the revision
#   $EVAL_DIR/skill/mail/scripts/mail.sh   under test
#   $EVAL_DIR/bin/tmail                    stand-in for the daemon-backed CLI
#   $EVAL_DIR/bin/ttasks                   stand-in that accepts `comment`
#   $EVAL_DIR/calls.log                    one line per tmail and ttasks call
#
# Give the actor the skill from $EVAL_DIR/skill/mail, run it in $EVAL_DIR
# with $EVAL_DIR/bin first on PATH and without TARIBOY_TOOLS_SOCKET. The real
# tmail without that socket acts as the customer on the host daemon, so the
# stand-ins must shadow it. Grade the actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
store_root=$(cd "$suite_root/../.." && pwd)
skill="$EVAL_DIR/skill/mail"

open_ids=()
dead=false
manifest=false
while [ $# -gt 0 ]; do
  case "$1" in
    --open) [ $# -ge 2 ] || { echo "--open needs an id" >&2; exit 2; }; open_ids+=("$2"); shift ;;
    --dead-letter) dead=true ;;
    --manifest) manifest=true ;;
    *) echo "usage: mail-cli.sh [--open ID]... [--dead-letter] [--manifest]" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$skill/scripts" "$EVAL_DIR/bin"
cp "$suite_root/SKILL.md" "$skill/"
cp "$suite_root/scripts/mail.sh" "$skill/scripts/"
: > "$EVAL_DIR/calls.log"
printf '%s\n' "${open_ids[@]+"${open_ids[@]}"}" > "$EVAL_DIR/bin/.open"
if $dead; then
  echo "m-20261025T081500Z-000009" > "$EVAL_DIR/bin/.dead"
else
  : > "$EVAL_DIR/bin/.dead"
fi

if $manifest; then
  mkdir -p "$EVAL_DIR/images/basic"
  cp "$store_root/images/basic/Tariboyfile.yaml" "$store_root/images/basic/skills-lock.json" "$EVAL_DIR/images/basic/"
fi

cat > "$EVAL_DIR/bin/tmail" <<'TMAIL_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
bin=$(cd "$(dirname "$0")" && pwd)
log="$bin/../calls.log"
stdin=""
for a in "$@"; do [ "$a" = - ] && { stdin=$(cat); break; }; done
{ printf '%q ' tmail "$@"; [ -z "$stdin" ] || printf '<stdin %q>' "$stdin"; printf '\n'; } >> "$log"
dl=m-20261025T081500Z-000009
known() { grep -qxF -- "$1" "$bin/.open" "$bin/.dead" 2>/dev/null; }
case "${1:-}" in
  ""|--help|-h)
    cat <<'HELP'
Usage: tmail <command> [args] [flags]

Commands:
  inbox      List the open letters in the mailbox, oldest first
  sent       List the letters you sent, newest first
  archive    List the closed letters, newest first, dead ones tagged
  show       Show one letter and its reply, if any
  send       Send a letter: a request unless --notice
  reply      Reply to a letter, which closes it
  requeue    Return one of your dead letters to the inbox
  close      Archive a letter without a reply (operator-only)
  read       Mark letters read (operator-only)
  unread     Count the open letters by sender and kind (operator-only)
  clear      Delete the open letters in an agent's inbox (operator-only)

send: tmail send --to PRINCIPAL[,PRINCIPAL] --subject S --text T [--deadline DURATION] [--notice]
reply: tmail reply ID TEXT [--ask]
HELP
    ;;
  inbox)
    n=0
    while read -r id; do
      [ -n "$id" ] || continue
      if [ "$id" = "$dl" ]; then
        echo "$id  from agent:release  kind message  attempts 0"; echo "  subject: Rollout window for build 40"
      else
        echo "$id  (the letter of the iteration prompt)"
      fi
      n=$((n+1))
    done < "$bin/.open"
    [ "$n" -gt 0 ] || echo "no open letters"
    ;;
  sent) echo "no sent letters" ;;
  archive)
    if [ -s "$bin/.dead" ]; then
      echo "m-20261025T081500Z-000009  from agent:release  kind message  dead:max_attempts"
      echo "  subject: Rollout window for build 40"
    else
      echo "no closed letters"
    fi
    ;;
  show)
    id=${2:-}; known "$id" || { echo "tmail: letter $id not found" >&2; exit 1; }
    if [ "$id" = "$dl" ]; then
      state=open; grep -qxF -- "$id" "$bin/.dead" && state=dead:max_attempts
      echo "id: $id"; echo "from: agent:release"; echo "kind: message"; echo "state: $state"
      echo "subject: Rollout window for build 40"; echo "text: Can build 40 roll out tonight between 22:00 and 23:00?"
    else
      echo "id: $id"; echo "state: open"; echo "(the letter of the iteration prompt)"
    fi
    ;;
  reply)
    id=${2:-}; [ $# -ge 3 ] || { echo "usage: tmail reply ID TEXT [--ask]" >&2; exit 2; }
    known "$id" || { echo "tmail: letter $id not found" >&2; exit 1; }
    kind=notice; for a in "$@"; do [ "$a" = --ask ] && kind=request; done
    echo "replied m-20261103T120000Z-000100 (message $kind)"; echo "closed $id"
    ;;
  send)
    to=""; prev=""
    for a in "$@"; do [ "$prev" = --to ] && to=$a; prev=$a; done
    [ -n "$to" ] || { echo "tmail send: --to is required" >&2; exit 2; }
    i=101; IFS=, read -ra rcpts <<< "$to"
    for r in "${rcpts[@]}"; do echo "sent m-20261103T120000Z-000$i to $r"; i=$((i+1)); done
    ;;
  requeue)
    id=${2:-}; grep -qxF -- "$id" "$bin/.dead" || { echo "tmail: no dead letter $id" >&2; exit 1; }
    : > "$bin/.dead"; echo "$id" >> "$bin/.open"
    echo "requeued $id"
    ;;
  close|read|unread|clear) echo "tmail $1: operator-only" >&2; exit 1 ;;
  *) echo "tmail: unknown command ${1}" >&2; exit 2 ;;
esac
TMAIL_CLI_EOF

cat > "$EVAL_DIR/bin/ttasks" <<'TTASKS_CLI_EOF'
#!/usr/bin/env bash
set -euo pipefail
bin=$(cd "$(dirname "$0")" && pwd)
{ printf '%q ' ttasks "$@"; printf '\n'; } >> "$bin/../calls.log"
case "${1:-}" in
  comment) [ $# -ge 3 ] || { echo "usage: ttasks comment KEY TEXT" >&2; exit 2; }; echo "id: 9001"; echo "task_key: $2" ;;
  *) echo "ttasks ${1:-}: not available in this sandbox" >&2; exit 127 ;;
esac
TTASKS_CLI_EOF

chmod +x "$EVAL_DIR/bin/tmail" "$EVAL_DIR/bin/ttasks"
