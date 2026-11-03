#!/usr/bin/env bash
# Fixture for the cli-text eval owning-skill-proposals: four Store skills that
# take text, each with a recording stand-in for its launcher.
#
# Usage: owning-skills.sh
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's current directory; the
#              fixture writes only inside it
#
# The fixture creates, for NAME in tasks, context, mail and status:
#   $EVAL_DIR/skills/NAME/SKILL.md          SKILL.md of the revision under test
#   $EVAL_DIR/skills/NAME/scripts/NAME.sh   stand-in launcher: appends its argv
#                                           as one JSON line to calls.jsonl
#   $EVAL_DIR/calls.jsonl                   empty at the start
#
# The actor only proposes snippets. To grade, run each proposed snippet with
# `bash` in $EVAL_DIR and compare the argv lines in calls.jsonl with the
# expected text byte for byte. The stand-ins call no daemon or service.
set -euo pipefail

: "${EVAL_DIR:?}"
store_skills=$(cd "$(dirname "$0")/../../.." && pwd)

: > "$EVAL_DIR/calls.jsonl"
for name in tasks context mail status; do
  skill="$EVAL_DIR/skills/$name"
  mkdir -p "$skill/scripts"
  cp "$store_skills/$name/SKILL.md" "$skill/SKILL.md"
  cat > "$skill/scripts/$name.sh" <<'LAUNCHER_STUB_EOF'
#!/usr/bin/env python3
import json
import sys
from pathlib import Path
log = Path(__file__).resolve().parents[3] / 'calls.jsonl'
with log.open('a') as out:
    out.write(json.dumps([Path(__file__).stem] + sys.argv[1:], ensure_ascii=False) + '\n')
print('ok')
LAUNCHER_STUB_EOF
  chmod +x "$skill/scripts/$name.sh"
done
