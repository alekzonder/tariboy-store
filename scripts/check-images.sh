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
  local canonical="$source/images/basic/iteration-finish.md"
  for image_dir in "$source"/images/*; do
    test -d "$image_dir" || continue
    local prompt="$image_dir/iteration-finish.md"
    if ! cmp -s "$canonical" "$prompt"; then
      printf 'images/%s/iteration-finish.md differs from images/basic/iteration-finish.md\n' "$(basename -- "$image_dir")" >&2
      return 1
    fi
  done
}

if test "${1:-}" = "--paths-only"; then
  check_paths "${2:-$repo_root}"
  exit
fi
if test "$#" -ne 0; then
  printf 'usage: %s [--paths-only [STORE_ROOT]]\n' "$0" >&2
  exit 64
fi

check_paths "$repo_root"

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
rm -rf -- "$source_copy/.git"
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
  "$tariboy_bin" --socket "$socket" image build --path "$image_dir" --name "$name" >/dev/null
done
