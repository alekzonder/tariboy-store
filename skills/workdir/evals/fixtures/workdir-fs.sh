#!/usr/bin/env bash
# Fixture for the workdir evals: the files a case names under ${EVAL_DIR}.
#
# Usage: workdir-fs.sh VARIANT
#   release-notes   case 4: the writer workdir and the installed release-notes
#                   skill with SKILL.md and scripts/render.py.
#   ops-cleanup     case 5: the ops workdir after OPS-12 is done, with the
#                   OPS-12 files, the OPS-15 task directory and the state
#                   directory of the active schedule scr-77.
#   data-convert    case 6: /srv/inbox/orders.csv and the empty DATA-4 workdir.
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The case prompt and expectations name every path with the ${EVAL_DIR}
# prefix; the runner replaces it with the case directory. Grade the actor on
# its answer and on the final state of these paths.
set -euo pipefail

: "${EVAL_DIR:?}"
variant=${1:?usage: workdir-fs.sh VARIANT}

case "$variant" in
  release-notes)
    agent="$EVAL_DIR/home/agent/.tariboy/agents/writer"
    skill="$agent/skills/release-notes"
    mkdir -p "$agent/workdir" "$skill/scripts"
    cat > "$skill/SKILL.md" <<'MD'
---
name: release-notes
description: Use when rendering release notes for a version to Markdown.
---

# Release notes

Render notes with `python3 scripts/render.py --version VERSION --out FILE`.
MD
    cat > "$skill/scripts/render.py" <<'PY'
#!/usr/bin/env python3
"""Render release notes for one version to a Markdown file."""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--version", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
with open(args.out, "w", encoding="utf-8") as out:
    out.write(f"# Release notes {args.version}\n\n- No changes recorded.\n")
PY
    chmod +x "$skill/scripts/render.py"
    ;;
  ops-cleanup)
    workdir="$EVAL_DIR/home/agent/.tariboy/agents/ops/workdir"
    mkdir -p "$workdir/OPS-12/skill-copy" "$workdir/OPS-12/eval-runs" \
      "$workdir/OPS-15" "$workdir/state/ops-15-pr-monitor"
    printf '#!/usr/bin/env python3\nprint("metrics")\n' > "$workdir/OPS-12/fetch-metrics.py"
    printf -- '---\nname: metrics\ndescription: Copy of the metrics skill for OPS-12.\n---\n' \
      > "$workdir/OPS-12/skill-copy/SKILL.md"
    printf 'case 1: pass\n' > "$workdir/OPS-12/eval-runs/run-1.txt"
    printf '# OPS-12 report\n\nKept artifact of OPS-12.\n' > "$workdir/OPS-12/report.md"
    printf 'OPS-15 work in progress\n' > "$workdir/OPS-15/notes.md"
    printf '{"pr": 15, "head": "abc1234"}\n' > "$workdir/state/ops-15-pr-monitor/state.json"
    ;;
  data-convert)
    mkdir -p "$EVAL_DIR/srv/inbox" "$EVAL_DIR/srv/agents/data/workdir"
    printf 'id,item,qty\n1,widget,3\n2,gadget,1\n' > "$EVAL_DIR/srv/inbox/orders.csv"
    ;;
  *)
    echo "workdir-fs.sh: unknown variant: $variant" >&2
    exit 2
    ;;
esac
