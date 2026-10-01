#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)

check_paths() {
  local source=$1
  local matches
  matches=$(rg -n --glob Tariboyfile.yaml '\$(CURRENT_VERSION_STORE|STORE)(/|$)|/home/agent/github/tariboy' "$source/images" || true)
  if test -n "$matches"; then
    printf '%s\n' "$matches" >&2
    return 1
  fi
  local duplicate
  duplicate=$(find "$source/images" -mindepth 2 -maxdepth 2 -name iteration-finish.md -print -quit)
  if test -n "$duplicate"; then
    printf '%s duplicates skills/loop/finish-iteration.md\n' "${duplicate#"$source/"}" >&2
    return 1
  fi
}

# `npx skills experimental_install` adds locked skills but never removes one
# dropped from the lock, so a checkout can keep a stale installed copy.
warn_stale_installs() {
  local source=$1
  local lock
  for lock in "$source"/images/*/skills-lock.json; do
    test -f "$lock" || continue
    python3 -B - "$source" "$lock" <<'PY'
import json
import pathlib
import sys

source, lock = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
installed = lock.parent / ".agents" / "skills"
if installed.is_dir():
    locked = set(json.loads(lock.read_text()).get("skills", {}))
    for entry in sorted(installed.iterdir()):
        if entry.name not in locked:
            print(
                f"warning: {entry.relative_to(source)} is not recorded in "
                f"{lock.relative_to(source)}",
                file=sys.stderr,
            )
PY
  done
}

if test "${1:-}" = "--paths-only"; then
  check_paths "${2:-$repo_root}"
  warn_stale_installs "${2:-$repo_root}"
  exit
fi
if test "$#" -ne 0; then
  printf 'usage: %s [--paths-only [STORE_ROOT]]\n' "$0" >&2
  exit 64
fi

check_paths "$repo_root"
warn_stale_installs "$repo_root"

tariboy_bin=$(command -v "${TARIBOY_BIN:-tariboy}")
tariboyd_bin=$(command -v "${TARIBOYD_BIN:-tariboyd}")
command -v npx >/dev/null

tmp=$(mktemp -d)
daemon_pid=
cleanup() {
  if test -n "$daemon_pid" && kill -0 "$daemon_pid" 2>/dev/null; then
    kill "$daemon_pid"
    wait "$daemon_pid" 2>/dev/null || true
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT
umask 077

source_copy="$tmp/store"
cp -a "$repo_root/." "$source_copy"
rm -rf -- "$source_copy/.git" "$source_copy"/images/*/.agents
for lock in "$source_copy"/images/*/skills-lock.json; do
  test -f "$lock" || continue
  if ! (cd -- "$(dirname -- "$lock")" && npx skills experimental_install) >"$tmp/restore.log" 2>&1; then
    sed -n '1,200p' "$tmp/restore.log" >&2
    exit 1
  fi
done

base="$tmp/base"
runtime="$tmp/runtime"
socket="$runtime/tariboyd.sock"
mkdir -p "$base" "$runtime"
TARIBOY_BASE_DIR="$base" TARIBOY_RUNTIME_DIR="$runtime" \
  "$tariboyd_bin" --listen "unix:$socket" --http-addr "" >"$tmp/daemon.log" 2>&1 &
daemon_pid=$!

for _ in $(seq 1 200); do
  test -S "$socket" && break
  kill -0 "$daemon_pid" 2>/dev/null || {
    sed -n '1,160p' "$tmp/daemon.log" >&2
    exit 1
  }
  sleep 0.05
done
test -S "$socket" || {
  sed -n '1,160p' "$tmp/daemon.log" >&2
  printf '%s\n' 'isolated tariboyd did not create its socket' >&2
  exit 1
}

for image_dir in "$source_copy"/images/*; do
  test -d "$image_dir" || continue
  name=$(basename -- "$image_dir")
  "$tariboy_bin" --socket "$socket" image validate --path "$image_dir" --name "$name" >/dev/null
  "$tariboy_bin" --socket "$socket" image build --path "$image_dir" --name "$name" --tag store-check >/dev/null
done
