#!/usr/bin/env bash
# Fixture for the whoami skill evals: the skill with a stand-in whoami CLI.
#
# Usage: whoami-cli.sh [--repo NAME]
#   --repo NAME   also make $EVAL_DIR a Git repository whose origin, README
#                 and history name a different agent and daemon version, as
#                 decoys the actor must not use
#
# The eval runner sets:
#   EVAL_DIR   the case directory and the actor's working directory; the
#              fixture writes only inside it
#
# The fixture creates:
#   $EVAL_DIR/skill/whoami/SKILL.md            the file of the revision under test
#   $EVAL_DIR/skill/whoami/scripts/whoami.sh   the stand-in for the daemon-backed CLI
#   $EVAL_DIR/skill/whoami/scripts/daemon.py   its daemon
#   $EVAL_DIR/calls.log                        one line per stand-in call, in order
#
# Give the actor the skill from $EVAL_DIR/skill/whoami and run it in
# $EVAL_DIR. No daemon socket is needed. The stand-in accepts the real CLI's
# arguments (`whoami.sh`, `--json`, `--help`), rejects others and prints in
# the real CLI's format. It reports:
#   agent: docs-writer
#   client_version: 0.104.2
#   cwd: /home/agent/github/handbook
#   daemon_version: 0.104.3
#   iteration: docs-writer-20260921091500-3
# The decoys of --repo are agent web-deployer and daemon 0.90.0. Grade the
# actor on its response and calls.log.
set -euo pipefail

: "${EVAL_DIR:?}"
suite_root=$(cd "$(dirname "$0")/../.." && pwd)
skill="$EVAL_DIR/skill/whoami"

repo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo=${2?}; shift 2 ;;
    *) echo "usage: whoami-cli.sh [--repo NAME]" >&2; exit 2 ;;
  esac
done

if [ -n "$repo" ]; then
  git -C "$EVAL_DIR" init -q -b main
  git -C "$EVAL_DIR" remote add origin "https://github.com/example/$repo.git"
  cat > "$EVAL_DIR/README.md" <<README_EOF
# $repo

Deployed by the Tariboy agent \`web-deployer\` on daemon 0.90.0.
README_EOF
  printf 'skill/\ncalls.log\n' > "$EVAL_DIR/.gitignore"
  git -C "$EVAL_DIR" add README.md .gitignore
  git -C "$EVAL_DIR" -c user.name=web-deployer -c user.email=web-deployer@example.invalid \
    commit -q -m "Pin tariboy daemon 0.90.0 for agent web-deployer"
fi

mkdir -p "$skill/scripts"
cp "$suite_root/SKILL.md" "$skill/"
: > "$EVAL_DIR/calls.log"

cat > "$skill/scripts/whoami.sh" <<'WHOAMI_CLI_EOF'
#!/bin/sh
exec python3 -B "$(dirname "$0")/daemon.py" "$@"
WHOAMI_CLI_EOF
chmod +x "$skill/scripts/whoami.sh"

cat > "$skill/scripts/daemon.py" <<'DAEMON_EOF'
import json, shlex, sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[3]
IDENTITY = {
    "agent": "docs-writer",
    "client_version": "0.104.2",
    "cwd": "/home/agent/github/handbook",
    "daemon_version": "0.104.3",
    "iteration": "docs-writer-20260921091500-3",
}

argv = sys.argv[1:]
with open(EVAL_DIR / "calls.log", "a") as log:
    log.write(" ".join(shlex.quote(a) for a in ["whoami.sh", *argv]) + "\n")
if argv in (["-h"], ["--help"]):
    print("usage: whoami.sh [--json]")
    sys.exit(0)
as_json = "--json" in argv
for a in argv:
    if a.startswith("--") and a != "--json":
        print(f"unknown flag --{a[2:].split('=', 1)[0]}", file=sys.stderr)
        sys.exit(2)
print(f"warning: client version {IDENTITY['client_version']} does not match daemon version "
      f"{IDENTITY['daemon_version']}; this client ({Path(__file__).with_name('whoami.sh')}) may not know the daemon's newer flags",
      file=sys.stderr)
if as_json:
    print(json.dumps(IDENTITY, separators=(",", ":")))
else:
    for k in sorted(IDENTITY): print(f"{k}: {IDENTITY[k]}")
DAEMON_EOF
