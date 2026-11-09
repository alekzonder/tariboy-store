#!/usr/bin/env bash
# Fixture for the image-improve workflow evals: a tiny Tariboy Store with one
# image and one workflow.
#
# Usage: store-repo.sh VARIANT
#   plain            main only; nothing started
#   changed          a task branch and worktree with one committed change (a
#                    tightened rule, a new eval case, image_version bumped),
#                    pushed; no pull request
#   head-moved       like changed, plus a second commit of the same change
#                    (a more exact eval prompt) pushed after the first one was
#                    verified
#   merged-workflow  a pull request that changed only workflows/demo/ and was
#                    merged on origin; the local main is behind; the task
#                    branch and worktree exist
#   merged-unbumped  a pull request that changed images/demo/instructions.md
#                    without a version bump and was merged on origin
#
# The workflow eval runner sets EVAL_DIR, EVAL_GITHUB_STATE and EVAL_VARS; the
# fixture writes only inside EVAL_DIR. The checkout is $EVAL_DIR/repo. Its
# origin is https://github.com/eval/demo-store; a repository-local
# url.insteadOf sends git to the bare repository $EVAL_DIR/origin.git, which
# the fake GitHub reads pull request heads from.
set -euo pipefail

variant=${1:?usage: store-repo.sh plain|changed|head-moved|merged-workflow|merged-unbumped}
: "${EVAL_DIR:?}" "${EVAL_GITHUB_STATE:?}" "${EVAL_VARS:?}"

export GIT_AUTHOR_NAME="Eval Fixture" GIT_AUTHOR_EMAIL="fixture@eval.invalid"
export GIT_COMMITTER_NAME="Eval Fixture" GIT_COMMITTER_EMAIL="fixture@eval.invalid"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z"

origin_url=https://github.com/eval/demo-store
bare="$EVAL_DIR/origin.git"
repo="$EVAL_DIR/repo"
branch=improve/tighten-failure-rule
worktree="$EVAL_DIR/worktrees/tighten-failure-rule"

git init -q --bare -b main "$bare"
git init -q -b main "$repo"
git -C "$repo" config user.name "Eval Creator"
git -C "$repo" config user.email "creator@eval.invalid"
git -C "$repo" config "url.$bare.insteadOf" "$origin_url"
git -C "$repo" remote add origin "$origin_url"

mkdir -p "$repo/images/demo/evals" "$repo/workflows/demo/statuses" "$repo/scripts"
cat >"$repo/images/demo/Tariboyfile.yaml" <<'YAML'
schema_version: 2
image_version: 0.1.0
plugins: []
skills: []
prompts:
    - file: ./instructions.md
YAML
cat >"$repo/images/demo/instructions.md" <<'MD'
# Demo agent

Answer the customer's question on its Native Task.

## Rules

- Report every failure in a task comment.
- Never delete a file you did not create.
MD
printf '%s\n' 'The demo image answers questions on tasks so that the customer gets a short, checked answer.' >"$repo/images/demo/ROLE.md"
cat >"$repo/images/demo/evals/evals.json" <<'JSON'
{
  "image_name": "demo",
  "evals": [
    {
      "id": "report-failure",
      "prompt": "A command failed. What do you do?",
      "expected_output": "Success criteria:\n- reports the failure in a task comment"
    }
  ]
}
JSON
cat >"$repo/workflows/demo/Workflowfile.yaml" <<'YAML'
schema_version: 1
name: demo
workflow_version: 0.1.0
initial_status: open
statuses:
    - id: open
      owner: customer
      instructions: ./statuses/open.md
      transitions:
        - {on: close, to: done}
    - id: done
      terminal: true
YAML
printf '%s\n' '# Open' '' 'Close the task when the question is answered.' >"$repo/workflows/demo/statuses/open.md"
printf '%s\n' 'The demo workflow takes a question to an answer so that no question is lost.' >"$repo/workflows/demo/ROLE.md"
cat >"$repo/scripts/check.py" <<'PY'
#!/usr/bin/env python3
"""The Store check of the demo repository: versions are SemVer, ROLE.md exists."""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1]
text = (root / "images/demo/Tariboyfile.yaml").read_text()
if not re.search(r"^image_version: \d+\.\d+\.\d+$", text, re.MULTILINE):
    sys.exit("images/demo: image_version is not SemVer")
for role in ("images/demo/ROLE.md", "workflows/demo/ROLE.md"):
    if not (root / role).read_text().strip():
        sys.exit(f"{role} is empty")
print("check: ok")
PY
printf '%s\n' '.PHONY: check' 'check:' $'\tpython3 scripts/check.py' >"$repo/Makefile"
cat >"$repo/AGENTS.md" <<'MD'
# demo-store

- Verification: `make check` from the repository root.
- Pull requests land on `main` from a task branch. Bump `image_version` of every changed image.
MD
mkdir -p "$repo/evidence"
printf '%s\n' '# Assessment as-301' '' 'The agent wrote "build failed" and stopped.' >"$repo/evidence/as-301.md"
printf '%s\n' '# Assessment as-302' '' 'The agent dropped the return code in two comments.' >"$repo/evidence/as-302.md"
printf '%s\n' '# Iteration demo-20260101000000-1' '' 'The agent ended after one failed command.' >"$repo/evidence/iteration-1.md"
printf '%s\n' '' 'The demo image never invents a result.' >>"$repo/images/demo/ROLE.md"
printf '__pycache__/\n' >"$repo/.gitignore"
git -C "$repo" add -A
git -C "$repo" commit -q -m "Add the demo image and workflow"
git -C "$repo" push -q origin main
git -C "$repo" fetch -q origin
git -C "$repo" branch -q --set-upstream-to=origin/main main

base_sha=$(git -C "$repo" rev-parse HEAD)
pulls='[]'
head_sha=
old_head_sha=
merge_sha=

make_change() {
  # Tighten the rule, add an eval case for it and bump the version.
  local dir=$1
  python3 - "$dir" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
instructions = root / "images/demo/instructions.md"
instructions.write_text(instructions.read_text().replace(
    "- Report every failure in a task comment.\n",
    "- Report every failure in a task comment, with the command and its exit status.\n"))
evals = root / "images/demo/evals/evals.json"
data = json.loads(evals.read_text())
data["evals"].append({
    "id": "report-failure-with-exit-status",
    "prompt": "A command failed with exit status 2. What does your comment contain?",
    "expected_output": "Success criteria:\n- the comment names the command and the exit status 2",
})
evals.write_text(json.dumps(data, indent=2) + "\n")
manifest = root / "images/demo/Tariboyfile.yaml"
manifest.write_text(manifest.read_text().replace("image_version: 0.1.0", "image_version: 0.1.1"))
PY
}

if test "$variant" != plain; then
  mkdir -p "$(dirname -- "$worktree")"
  git -C "$repo" worktree add -q -b "$branch" "$worktree" main
  case "$variant" in
    changed|head-moved)
      make_change "$worktree"
      git -C "$worktree" commit -q -am "Tighten the failure rule and add its eval"
      git -C "$worktree" push -q -u origin "$branch"
      head_sha=$(git -C "$worktree" rev-parse HEAD)
      if test "$variant" = head-moved; then
        old_head_sha=$head_sha
        # A second commit of the same change: the eval prompt is made more exact.
        sed -i 's/What does your comment contain?/What does your comment contain? Name every item./' "$worktree/images/demo/evals/evals.json"
        git -C "$worktree" commit -q -am "Make the eval prompt more exact"
        git -C "$worktree" push -q origin "$branch"
        head_sha=$(git -C "$worktree" rev-parse HEAD)
      fi
      ;;
    merged-workflow)
      printf '\nClose it with the outcome close.\n' >>"$worktree/workflows/demo/statuses/open.md"
      python3 - "$worktree/workflows/demo/Workflowfile.yaml" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
path.write_text(path.read_text().replace("workflow_version: 0.1.0", "workflow_version: 0.1.1"))
PY
      git -C "$worktree" commit -q -am "Reword the open status"
      git -C "$worktree" push -q -u origin "$branch"
      head_sha=$(git -C "$worktree" rev-parse HEAD)
      ;;
    merged-unbumped)
      printf -- '- Ask when a rule is unclear.\n' >>"$worktree/images/demo/instructions.md"
      git -C "$worktree" commit -q -am "Add a rule about unclear rules"
      git -C "$worktree" push -q -u origin "$branch"
      head_sha=$(git -C "$worktree" rev-parse HEAD)
      ;;
  esac
fi

case "$variant" in
  merged-workflow|merged-unbumped)
    # Merge commit on origin: one new commit on main with the branch's tree.
    tree=$(git --git-dir "$bare" rev-parse "$head_sha^{tree}")
    merge_sha=$(git --git-dir "$bare" commit-tree "$tree" -p "$base_sha" -m "Merge pull request #7")
    git --git-dir "$bare" update-ref refs/heads/main "$merge_sha"
    pulls=$(printf '[{"number": 7, "head": "%s", "base": "main", "title": "Change the demo store", "body": "Changes the demo store.", "state": "closed", "merged": true, "merge_commit_sha": "%s", "head_sha": "%s"}]' "$branch" "$merge_sha" "$head_sha")
    ;;
esac

local_main=$(git -C "$repo" rev-parse main)

cat >"$EVAL_GITHUB_STATE" <<JSON
{"repos": {"eval/demo-store": {"bare": "$bare", "default_branch": "main", "pulls": $pulls}}}
JSON

cat >"$EVAL_VARS" <<JSON
{
  "repo": "$repo",
  "worktree": "$worktree",
  "branch": "$branch",
  "base_sha": "$base_sha",
  "head_sha": "$head_sha",
  "old_head_sha": "$old_head_sha",
  "merge_sha": "$merge_sha",
  "local_main": "$local_main",
  "pr_url": "https://github.com/eval/demo-store/pull/7"
}
JSON
