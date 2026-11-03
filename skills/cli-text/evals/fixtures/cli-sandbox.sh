#!/usr/bin/env bash
# Fixture for the cli-text evals: the disposable sandbox the actor works in.
#
# Usage: cli-sandbox.sh stubs|git
#   stubs  recording stand-ins ./bin/ttasks and ./bin/gh
#   git    a Git repository with one staged change
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's current directory; the
#              fixture writes only inside it
#
# The fixture creates, for `stubs`:
#   $EVAL_DIR/bin/ttasks     `--help` prints `usage: ttasks comment KEY BODY`
#   $EVAL_DIR/bin/gh         `pr create --help` lists --title, --body, --body-file
#   $EVAL_DIR/records.json   one entry per CLI call: name, argv and, for
#                            --body-file, the file content
# and, for `git`:
#   $EVAL_DIR/.git           one commit; parser.txt has one staged change
#
# Grade `stubs` cases on records.json and `git` cases on
# `git -C "$EVAL_DIR" log -1 --format=%B`; read the actor's tool calls for an
# extra shell layer.
set -euo pipefail

: "${EVAL_DIR:?}"
mkdir -p "$EVAL_DIR"

case "${1:-}" in
  stubs)
    mkdir -p "$EVAL_DIR/bin"
    cat > "$EVAL_DIR/bin/ttasks" <<'CLI_STUB_EOF'
#!/usr/bin/env python3
import json
import sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
if '--help' in args:
    if name == 'ttasks':
        print('usage: ttasks comment KEY BODY')
    else:
        print('usage: gh pr create --title TEXT (--body TEXT | --body-file FILE)')
    sys.exit(0)
record = {'cmd': name, 'argv': args}
if '--body-file' in args:
    body_file = args[args.index('--body-file') + 1]
    record['body_file'] = sys.stdin.read() if body_file == '-' else Path(body_file).read_text()
log = Path(__file__).resolve().parent.parent / 'records.json'
records = json.loads(log.read_text()) if log.exists() else []
records.append(record)
log.write_text(json.dumps(records, ensure_ascii=False, indent=1))
print('ok')
CLI_STUB_EOF
    cp "$EVAL_DIR/bin/ttasks" "$EVAL_DIR/bin/gh"
    chmod +x "$EVAL_DIR/bin/ttasks" "$EVAL_DIR/bin/gh"
    ;;
  git)
    git -C "$EVAL_DIR" init -q
    git -C "$EVAL_DIR" config user.name eval
    git -C "$EVAL_DIR" config user.email eval@example.invalid
    printf 'a\n' > "$EVAL_DIR/parser.txt"
    git -C "$EVAL_DIR" add parser.txt
    git -C "$EVAL_DIR" commit -qm init
    printf 'b\n' >> "$EVAL_DIR/parser.txt"
    git -C "$EVAL_DIR" add parser.txt
    ;;
  *)
    echo "usage: cli-sandbox.sh stubs|git" >&2
    exit 2
    ;;
esac
