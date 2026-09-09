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
mkdir -p "$fixture/images/basic" "$fixture/images/example"
printf '%s\n' canonical >"$fixture/images/basic/iteration-finish.md"
printf '%s\n' drifted >"$fixture/images/example/iteration-finish.md"
if output=$("$root/scripts/check-images.sh" --paths-only "$fixture" 2>&1); then
  printf '%s\n' 'expected finish prompt drift to fail' >&2
  exit 1
fi
case "$output" in
  *'images/example/iteration-finish.md differs from images/basic/iteration-finish.md'*) ;;
  *)
    printf 'unexpected diagnostic: %s\n' "$output" >&2
    exit 1
    ;;
esac
