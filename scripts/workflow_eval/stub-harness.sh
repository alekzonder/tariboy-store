#!/usr/bin/env bash
# Stub harness for `workflow-eval.py --render-only`. The daemon runs it in
# place of a model harness when TARIBOY_STUB_HARNESS points here: it receives
# the iteration's prompt path as $1, does no work, finishes the iteration
# through the tools socket and exits. The daemon keeps the prompt in the
# iteration's PROMPT.md, which the runner checks.
set -eu

if [ "${1:-}" = "--version" ]; then
  printf '%s\n' '2.1.227'
  exit 0
fi

curl -sf --unix-socket "$TARIBOY_TOOLS_SOCKET" -H 'content-type: application/json' \
  -X POST "http://localhost/tools/loop/done" -d '{"idle":true}' >/dev/null 2>&1 || true
