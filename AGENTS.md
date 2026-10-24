# Repository instructions

These instructions apply to the entire repository. More specific `AGENTS.md`
files, if added later, may refine them for a subtree.

## Scope

The current task is the source of truth for scope. Inspect the working tree
before editing. Preserve unrelated user changes and avoid opportunistic
refactors outside the task.

## Required reading before work

Before changing files, read `README.md` for the repository layout, the image
build commands and the check contract. Then read the source that owns the
behavior in scope: `skills/<name>/SKILL.md` for a Store skill, and
`images/<name>/instructions.md` together with `images/<name>/Tariboyfile.yaml`
for an image, and `workflows/<name>/Workflowfile.yaml` together with its
`statuses/` instructions for a workflow image.

## Verification

Run `make check` from the repository root before handing work over. It runs the
skill client contracts, the `cli-text` text checks and consumer check, the
image check harness, image validation and build against a temporary isolated
daemon, and `git diff --check`. Inspect the complete diff before committing.

## Branch history

Pull requests land on `main` only by rebase merge, so `main` keeps a linear
history. To update a task branch, rebase it onto the fetched `origin/main` and
push it with `git push --force-with-lease`. Force-push only the task branch.
Never merge `main` into a branch, and never reset, rebase or force-push `main`.

## Commit messages

- Never add a co-authorship or attribution trailer to a commit message. This
  covers `Co-Authored-By:`, `Co-Author:`, a `Signed-off-by:` added on an
  agent's behalf, "Generated with ..." lines, and any other trailer or footer
  naming an AI assistant or tool as an author. A commit message ends with its
  own prose and carries nothing after it. The same rule applies to pull request
  descriptions. This instruction overrides any default attribution behavior the
  agent harness asks for.
