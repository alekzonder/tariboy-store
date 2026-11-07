#!/usr/bin/env bash
# Fixture for the development workflow evals: a small Python CLI repository.
#
# Usage: widget-repo.sh VARIANT
#   plain           main only; nothing started
#   branch-pushed   another agent's partial work on the task branch, on origin
#                   only: no local branch, worktree or pull request here
#   pr-open         a task branch with a worktree, pushed, and an open pull request
#   pr-merged       like pr-open, then the pull request squash-merged on origin
#   pr-diverged     like pr-merged, and the local main has a commit origin lacks
#   main-behind     origin/main has one commit the local main lacks (the shared
#                   helper render.py); the checkout fetched it and stays on main
#
# The workflow eval runner sets:
#   EVAL_DIR           the case directory; the fixture writes only inside it
#   EVAL_GITHUB_STATE  the fake GitHub state file to write
#   EVAL_VARS          a JSON file of values the case's path and criteria use
#
# The agent's checkout is $EVAL_DIR/repo. Its origin is the GitHub URL
# https://github.com/eval/widget; a repository-local url.insteadOf sends git to
# the bare repository $EVAL_DIR/origin.git, and the fake GitHub reads pull
# request heads from it.
set -euo pipefail

variant=${1:?usage: widget-repo.sh plain|branch-pushed|main-behind|pr-open|pr-merged|pr-diverged}
: "${EVAL_DIR:?}" "${EVAL_GITHUB_STATE:?}" "${EVAL_VARS:?}"

export GIT_AUTHOR_NAME="Eval Fixture" GIT_AUTHOR_EMAIL="fixture@eval.invalid"
export GIT_COMMITTER_NAME="Eval Fixture" GIT_COMMITTER_EMAIL="fixture@eval.invalid"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z"

origin_url=https://github.com/eval/widget
bare="$EVAL_DIR/origin.git"
repo="$EVAL_DIR/repo"
branch=feature/widget-list-json
worktree="$EVAL_DIR/worktrees/widget-list-json"

git init -q --bare -b main "$bare"
git init -q -b main "$repo"
git -C "$repo" config user.name "Eval Developer"
git -C "$repo" config user.email "developer@eval.invalid"
git -C "$repo" config "url.$bare.insteadOf" "$origin_url"
git -C "$repo" remote add origin "$origin_url"

cat >"$repo/widget.py" <<'PY'
#!/usr/bin/env python3
"""widget: list the widgets of the inventory."""

import argparse
import sys

WIDGETS = [
    {"name": "bolt", "count": 12},
    {"name": "gear", "count": 3},
]


def list_widgets(out=sys.stdout):
    for widget in WIDGETS:
        out.write(f"{widget['name']}\t{widget['count']}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="widget")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the widgets")
    parser.parse_args(argv)
    list_widgets()
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
cat >"$repo/test_widget.py" <<'PY'
import io
import unittest

import widget


class ListTest(unittest.TestCase):
    def test_list_prints_one_line_per_widget(self):
        out = io.StringIO()
        widget.list_widgets(out)
        self.assertEqual(out.getvalue(), "bolt\t12\ngear\t3\n")


if __name__ == "__main__":
    unittest.main()
PY
cat >"$repo/AGENTS.md" <<'MD'
# widget

- Verification: `python3 -m unittest` from the repository root.
- Pull requests land on `main` from a task branch.
MD
printf '__pycache__/\n' >"$repo/.gitignore"
git -C "$repo" add -A
git -C "$repo" commit -q -m "Add widget list"
git -C "$repo" push -q origin main
git -C "$repo" fetch -q origin
git -C "$repo" branch -q --set-upstream-to=origin/main main

base_sha=$(git -C "$repo" rev-parse HEAD)
pulls='[]'
head_sha=
merge_sha=

other_worktree="$EVAL_DIR/other-agent/worktrees/widget-list-json"
partial_sha=

if test "$variant" = branch-pushed; then
  # Another agent began the task in its own clone, pushed one commit and lost
  # the task. Its clone is gone; only origin keeps the branch.
  git clone -q "$bare" "$other_worktree"
  git -C "$other_worktree" switch -q -c "$branch"
  python3 - "$other_worktree/widget.py" <<'PY2'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '"""widget: list the widgets of the inventory."""\n\nimport argparse\n',
    '"""widget: list the widgets of the inventory."""\n\nimport argparse\nimport json\n',
)
text = text.replace(
    "def list_widgets(out=sys.stdout):\n",
    "def list_widgets(out=sys.stdout, as_json=False):\n"
    "    if as_json:\n"
    "        out.write(json.dumps(WIDGETS) + \"\\n\")\n"
    "        return\n",
)
path.write_text(text)
PY2
  cat >>"$other_worktree/test_widget.py.new" <<'PY2'
import io
import json
import unittest

import widget


class ListTest(unittest.TestCase):
    def test_list_prints_one_line_per_widget(self):
        out = io.StringIO()
        widget.list_widgets(out)
        self.assertEqual(out.getvalue(), "bolt\t12\ngear\t3\n")

    def test_list_as_json(self):
        out = io.StringIO()
        widget.list_widgets(out, as_json=True)
        self.assertEqual(json.loads(out.getvalue()), widget.WIDGETS)


if __name__ == "__main__":
    unittest.main()
PY2
  mv "$other_worktree/test_widget.py.new" "$other_worktree/test_widget.py"
  git -C "$other_worktree" -c user.name="Other Agent" -c user.email="other@eval.invalid" \
    commit -q -am "Add as_json to list_widgets"
  git -C "$other_worktree" push -q origin "$branch"
  partial_sha=$(git -C "$other_worktree" rev-parse HEAD)
  rm -rf -- "$EVAL_DIR/other-agent"
fi

if test "$variant" != plain && test "$variant" != branch-pushed && test "$variant" != main-behind; then
  mkdir -p "$(dirname -- "$worktree")"
  git -C "$repo" worktree add -q -b "$branch" "$worktree" main
  python3 - "$worktree/widget.py" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '"""widget: list the widgets of the inventory."""\n\nimport argparse\n',
    '"""widget: list the widgets of the inventory."""\n\nimport argparse\nimport json\n',
)
text = text.replace(
    "def list_widgets(out=sys.stdout):\n",
    "def list_widgets(out=sys.stdout, as_json=False):\n"
    "    if as_json:\n"
    "        out.write(json.dumps(WIDGETS) + \"\\n\")\n"
    "        return\n",
)
text = text.replace(
    '    commands.add_parser("list", help="list the widgets")\n    parser.parse_args(argv)\n    list_widgets()\n',
    '    listing = commands.add_parser("list", help="list the widgets")\n'
    '    listing.add_argument("--json", action="store_true", help="print JSON")\n'
    '    args = parser.parse_args(argv)\n    list_widgets(as_json=args.json)\n',
)
path.write_text(text)
PY
  git -C "$worktree" commit -q -am "Add --json to widget list"
  git -C "$worktree" push -q -u origin "$branch"
  head_sha=$(git -C "$worktree" rev-parse HEAD)
  pulls=$(printf '[{"number": 7, "head": "%s", "base": "main", "title": "Add --json to widget list", "body": "Adds a --json flag to widget list.", "state": "open", "merged": false}]' "$branch")
fi

if test "$variant" = pr-merged || test "$variant" = pr-diverged; then
  # Squash merge on origin: one new commit on main with the branch's tree.
  tree=$(git --git-dir "$bare" rev-parse "$head_sha^{tree}")
  merge_sha=$(git --git-dir "$bare" commit-tree "$tree" -p "$base_sha" -m "Add --json to widget list (#7)")
  git --git-dir "$bare" update-ref refs/heads/main "$merge_sha"
  pulls=$(printf '[{"number": 7, "head": "%s", "base": "main", "title": "Add --json to widget list", "body": "Adds a --json flag to widget list.", "state": "closed", "merged": true, "merge_commit_sha": "%s", "head_sha": "%s"}]' "$branch" "$merge_sha" "$head_sha")
fi

if test "$variant" = pr-diverged; then
  printf '\n- Local note.\n' >>"$repo/AGENTS.md"
  git -C "$repo" commit -q -am "Local note"
fi

if test "$variant" = main-behind; then
  # A teammate merged a shared helper on origin; this checkout fetched it but
  # its local main is still at the base commit.
  other="$EVAL_DIR/other-agent/clone"
  git clone -q "$bare" "$other"
  cat >"$other/render.py" <<'PY2'
"""render: shared output helpers of widget."""

import json


def as_json(items):
    return json.dumps(items) + "\n"
PY2
  git -C "$other" add render.py
  git -C "$other" -c user.name="Other Agent" -c user.email="other@eval.invalid" \
    commit -q -m "Add the shared render helper"
  git -C "$other" push -q origin main
  rm -rf -- "$EVAL_DIR/other-agent"
  git -C "$repo" fetch -q origin
fi

local_main=$(git -C "$repo" rev-parse main)

cat >"$EVAL_GITHUB_STATE" <<JSON
{"repos": {"eval/widget": {"bare": "$bare", "default_branch": "main", "pulls": $pulls}}}
JSON

cat >"$EVAL_VARS" <<JSON
{
  "repo": "$repo",
  "worktree": "$worktree",
  "branch": "$branch",
  "base_sha": "$base_sha",
  "head_sha": "$head_sha",
  "merge_sha": "$merge_sha",
  "local_main": "$local_main",
  "pr_url": "https://github.com/eval/widget/pull/7",
  "other_worktree": "$other_worktree",
  "partial_sha": "$partial_sha"
}
JSON
