#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT

mkdir -p "$fixture/images/example"
printf '%s\n' \
  'schema_version: 2' \
  'plugins: []' \
  'skills:' \
  '  - dir: $CURRENT_VERSION_STORE/skills/whoami' \
  'prompts: []' >"$fixture/images/example/Tariboyfile.yaml"

if output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf '%s\n' 'expected forbidden Store path to fail' >&2
  exit 1
fi
case "$output" in
  *'images/example/Tariboyfile.yaml'*'$CURRENT_VERSION_STORE'*) ;;
  *)
    printf 'unexpected diagnostic: %s\n' "$output" >&2
    exit 1
    ;;
esac

rm -rf -- "$fixture"
mkdir -p "$fixture/skills/loop" "$fixture/images/example"
printf '%s\n' canonical >"$fixture/skills/loop/finish-iteration.md"
printf '%s\n' canonical >"$fixture/images/example/iteration-finish.md"
if output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf '%s\n' 'expected image-local finish prompt to fail' >&2
  exit 1
fi
case "$output" in
  *'images/example/iteration-finish.md duplicates skills/loop/finish-iteration.md'*) ;;
  *)
    printf 'unexpected diagnostic: %s\n' "$output" >&2
    exit 1
    ;;
esac

rm -rf -- "$fixture"
mkdir -p "$fixture/images/example/.agents/skills/locked" \
  "$fixture/images/example/.agents/skills/removed"
printf '%s\n' '{"version": 1, "skills": {"locked": {"source": "../../skills/locked", "sourceType": "local"}}}' \
  >"$fixture/images/example/skills-lock.json"
if ! output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf 'expected stale installation to warn, not fail: %s\n' "$output" >&2
  exit 1
fi
case "$output" in
  *'warning: images/example/.agents/skills/removed is not recorded in images/example/skills-lock.json'*) ;;
  *)
    printf 'missing stale installation warning: %s\n' "$output" >&2
    exit 1
    ;;
esac
case "$output" in
  *'skills/locked'*)
    printf 'locked installation reported as stale: %s\n' "$output" >&2
    exit 1
    ;;
esac

rm -rf -- "$fixture"
mkdir -p "$fixture/workflows/example"
printf '%s\n' \
  'schema_version: 1' \
  'name: example' \
  'initial_status: /home/agent/github/tariboy/scripts/check.sh' >"$fixture/workflows/example/Workflowfile.yaml"
if output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf '%s\n' 'expected forbidden checkout path in a workflow to fail' >&2
  exit 1
fi
case "$output" in
  *'workflows/example/Workflowfile.yaml'*'/home/agent/github/tariboy'*) ;;
  *)
    printf 'unexpected diagnostic: %s\n' "$output" >&2
    exit 1
    ;;
esac

rm -rf -- "$fixture"
mkdir -p "$fixture/workflows/example/scripts" "$fixture/workflows/example/statuses"
printf '%s\n' 'schema_version: 1' 'name: example' >"$fixture/workflows/example/Workflowfile.yaml"
printf '%s\n' '#!/bin/sh' 'exit 0' >"$fixture/workflows/example/scripts/check.sh"
printf '%s\n' 'Do the work.' >"$fixture/workflows/example/statuses/work.md"
if ! output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf 'expected a clean workflow to pass: %s\n' "$output" >&2
  exit 1
fi

printf '%s\n' 'Read $CURRENT_VERSION_STORE/skills/tasks first.' \
  >"$fixture/workflows/example/statuses/work.md"
if output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf '%s\n' 'expected a forbidden Store path in status instructions to fail' >&2
  exit 1
fi
case "$output" in
  *'workflows/example/statuses/work.md'*'$CURRENT_VERSION_STORE'*) ;;
  *)
    printf 'unexpected diagnostic: %s\n' "$output" >&2
    exit 1
    ;;
esac
