#!/usr/bin/env bash
# Fixture for the tariboy-image-creator image evals: the files a case names
# under ${EVAL_DIR}.
#
# Usage: case-fs.sh VARIANT
#   lumen-review      case customer-vcs-silent-customer-wait: the installed
#                     lumen-review skill with scripts/closure-poll.sh, the
#                     Store AGENTS.md, the img-140 worktree and the workdir.
#   role-md-conflict  case role-md-conflict-not-silent: the Store
#                     ${EVAL_DIR}/tmp/store with images/reviewer and its ROLE.md.
#   role-md-meaning   case role-md-meaning-in-instructions: the Store
#                     ${EVAL_DIR}/tmp/store with images/support, its
#                     instructions.md and ROLE.md.
#   workflow-docs     case workflow-task-routes-to-workflow-authoring:
#                     ${EVAL_DIR}/.fixture-bin/tariboy, which prints the help
#                     of `tariboy workflow` of the host CLI and refuses every
#                     other command.
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The case prompt and expectations name every path with the ${EVAL_DIR}
# prefix; the runner replaces it with the case directory. The runner puts
# ${EVAL_DIR}/.fixture-bin first in the actor's PATH.
set -euo pipefail

: "${EVAL_DIR:?}"
variant=${1:?usage: case-fs.sh VARIANT}

write_skill() { # DIR NAME DESCRIPTION
  mkdir -p "$1"
  printf -- '---\nname: %s\ndescription: %s\n---\n\n# %s\n\n%s\n' "$2" "$3" "$2" "$3" > "$1/SKILL.md"
}

case "$variant" in
  lumen-review)
    skill="$EVAL_DIR/home/agent/.tariboy/agents/img/skills/lumen-review"
    store="$EVAL_DIR/home/agent/lumen/store"
    mkdir -p "$skill/scripts" "$store" "$EVAL_DIR/home/agent/lumen/wt/img-140" \
      "$EVAL_DIR/home/agent/.tariboy/agents/img/workdir"
    cat > "$skill/SKILL.md" <<'MD'
---
name: lumen-review
description: Use when observing the closure of a Lumen review request.
---

# Lumen review

Poll one review: `scripts/closure-poll.sh REVIEW_ID --state-dir DIR`, run by
its absolute path. The script keeps its last observation in `DIR/last.json`.

| Exit | Meaning |
| --- | --- |
| 0 | first observation or a change; JSON facts on stdout |
| 111 | unchanged |
| 3 | data or parse error |
| 4 | `LUMEN_TOKEN` or the `lm` binary is missing |

Authoritative state: `lm review show REVIEW_ID --json`, fields `state`
(`open`, `closed`, `merged`) and `merge_commit`.
MD
    cat > "$skill/scripts/closure-poll.sh" <<'SH'
#!/usr/bin/env bash
# Poll the closure of one Lumen review. See ../SKILL.md for the exit codes.
set -euo pipefail
review=${1:?usage: closure-poll.sh REVIEW_ID --state-dir DIR}
[ "${2:-}" = --state-dir ] && [ -n "${3:-}" ] || { echo "usage: closure-poll.sh REVIEW_ID --state-dir DIR" >&2; exit 3; }
dir=$3
command -v lm >/dev/null && [ -n "${LUMEN_TOKEN:-}" ] || exit 4
facts=$(lm review show "$review" --json) || exit 3
mkdir -p "$dir"
if [ -f "$dir/last.json" ] && [ "$(cat "$dir/last.json")" = "$facts" ]; then
  exit 111
fi
printf '%s\n' "$facts" > "$dir/last.json"
printf '%s\n' "$facts"
SH
    chmod +x "$skill/scripts/closure-poll.sh"
    cat > "$store/AGENTS.md" <<'MD'
# Store instructions

Review closure poll: run `scripts/closure-poll.sh REVIEW_ID --state-dir DIR`
from the packaged `lumen-review` skill by its absolute path. It prints JSON
facts and exits 0 on the first observation or a change, 111 when unchanged,
3 on a data or parse error, 4 when the `LUMEN_TOKEN` credential or the `lm`
binary is missing. Authoritative state: `lm review show REVIEW_ID --json`
(fields `state`: open|closed|merged, `merge_commit`).
MD
    ;;
  role-md-conflict)
    image="$EVAL_DIR/tmp/store/images/reviewer"
    mkdir -p "$image/evals"
    printf 'schema_version: 2\nimage_version: 0.4.0\nskills: []\n' > "$image/Tariboyfile.yaml"
    printf '# Reviewer\n\nWrite the review of a pull request. Publish it on GitHub only after the customer approves it on the task.\n' \
      > "$image/instructions.md"
    write_skill "$image/skills/pull-request-review" pull-request-review \
      'Use when reviewing a pull request and publishing the review after approval.'
    printf '{\n  "image_name": "reviewer",\n  "evals": []\n}\n' > "$image/evals/evals.json"
    cat > "$image/ROLE.md" <<'MD'
# Роль: reviewer

## Что требуется от агента
- Агент пишет ревью pull request.
- Агент публикует ревью на GitHub только после одобрения заказчика.
MD
    ;;
  role-md-meaning)
    image="$EVAL_DIR/tmp/store/images/support"
    mkdir -p "$image"
    cat > "$image/instructions.md" <<'MD'
# Support

- Answer customers with `ttasks comment`.
- Read the `support-faq` skill first.
- Hand refund questions to the customer.
- Never change product code.
MD
    cat > "$image/ROLE.md" <<'MD'
# support

The support agent answers the customers of queue SUP on their tasks. The image exists so that customers get a quick, correct answer, and so that decisions on money stay with the customer.
MD
    ;;
  workflow-docs)
    bin="$EVAL_DIR/.fixture-bin"
    mkdir -p "$bin"
    help="$bin/tariboy-workflow-help.txt"
    if command -v tariboy >/dev/null; then
      tariboy workflow --help > "$help" 2>&1 || true
      for sub in build inspect ls rm validate version; do
        { printf '\n$ tariboy workflow %s --help\n' "$sub"; tariboy workflow "$sub" --help 2>&1 || true; } >> "$help"
      done
    else
      echo "tariboy workflow help: the tariboy CLI is not installed on the eval host" > "$help"
    fi
    cat > "$bin/tariboy" <<SH
#!/bin/sh
# Eval stub: prints the recorded help of \`tariboy workflow\`; every other command is refused.
case "\$*" in
  "workflow --help"|"workflow help"|"workflow"|"workflow "*" --help") cat "$help" ;;
  *) echo "tariboy: not available in this sandbox" >&2; exit 127 ;;
esac
SH
    chmod +x "$bin/tariboy"
    ;;
  *)
    echo "case-fs.sh: unknown variant: $variant" >&2
    exit 2
    ;;
esac
