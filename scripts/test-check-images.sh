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
