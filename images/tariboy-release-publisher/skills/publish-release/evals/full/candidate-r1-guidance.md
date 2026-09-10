---
name: publish-release
description: Use when preparing, publishing or recovering a Tariboy product release, choosing a SemVer bump, updating CHANGELOG, or checking release workflow and artifacts.
---

# Publish a Tariboy Release

One approved source SHA becomes one checked release commit and one immutable
annotated `vMAJOR.MINOR.PATCH` tag. Publication includes the release artifacts.

## Task and recorded plan

**REQUIRED:** Use `tasks`. For a new release, use `whoami` for your agent name,
then create a root with `ttasks create --queue TARI --assignee AGENT --title
'Publish Tariboy release'`. Use a stable request idempotency key for retries.
Record the supplied customer and repository, mark it `in_progress`, and use
`goal` to select it if no Goal is active. If a release task already exists in
runtime/context, read it and resume it. Never create another task for a restart.
Ask on that task for any missing customer/repository information.

Read repository instructions and inspect clean main, worktrees and its configured
upstream (`branch.main.remote`, `branch.main.merge`, requiring `refs/heads/main`).
Preserve unrelated changes; dirty main, divergence or ambiguous upstream blocks
integration. Fetch main and tags without force; fetching metadata is allowed
before approval, changing files/main or creating branches/worktrees is not.
Record the fetched main SHA as the proposed source, not a moving branch name.

Inspect tag history, every commit and the complete diff to that SHA. Use the
highest stable `vMAJOR.MINOR.PATCH` release tag reachable from that SHA; verify
its remote target and ancestry. Exclude prerelease and unrelated-branch tags.
If reachable tags, remote refs and declared versions disagree, or there is no
reachable release tag, ask the customer for an explicit baseline/version plan;
do not guess a baseline or reuse the canonical version as a new bump.

Choose the highest impact in the actual diff:

| Change | Bump |
| --- | --- |
| Fix, refactor, tooling or docs only | patch |
| New user-facing capability | minor |
| Intentional incompatible change on 0.x | minor |
| Intentional incompatible change on 1.x+ | major |

Reset lower components. Explain conflicts with an explicitly requested version
in the plan. If there is nothing to release, record that and ask for the
customer's decision. Require the proposed tag to be absent remotely; an existing
tag is reusable only as verified recovery of this task's exact release commit.

Find and read the repository-owned `scripts/set-version.sh`, its allowlist
`scripts/version-pinned-files.txt`, release declaration and release workflow.
Do not copy the script or replace it with global search/replace.

The task's approval question must contain these fields:

- Repository/upstream, previous tag and SHA, proposed source SHA and full range.
- Exact next version and SemVer rationale based on the diff.
- Draft CHANGELOG entry and expected changed files.
- Worktree/branch, version command, checks, direct main merge/push and annotated
  tag publication, matching workflow/assets verification and cleanup.

Use `ttasks ask KEY user:LOGIN TEXT` with the supplied customer's identity (or
the task packet's declared question action). **Wait for its recorded answer
before repository mutation.** An urgent request to release is not plan approval.
Reuse approval for unchanged inputs. If the fetched source changes, reanalyze
and ask for approval of the revised SHA/version/changelog before proceeding.

## Approved branch and changelog

Confirm approval and refresh remote state. Fast-forward clean local main to the
approved source, then create one separate worktree and release branch from it.
Record both on TARI; recover them on retry. Never reset, stash customer edits,
force-push or silently rebase around a changed source.

In that clean worktree, load Rust if needed and run the existing command first:

```bash
. "$HOME/.cargo/env"
scripts/set-version.sh MAJOR.MINOR.PATCH
```

Then update root `CHANGELOG.md` using Keep a Changelog: newest version first,
`## [X.Y.Z] - YYYY-MM-DD`, concise user-visible entries under applicable Added,
Changed, Deprecated, Removed, Fixed or Security headings, and a compare link
from the previous tag to the new tag using the verified repository URL. Preserve
released history and unrelated Unreleased entries; move only changes included
in this release. Create the file if absent. Describe compatibility/migration
impact; avoid a raw commit dump or empty categories.

Run the repository's focused release checks:

```bash
make desktop-version-check
make desktop-lock-check
go test ./scripts/...
git diff --check
git diff
```

Also inspect staged and untracked files. Require only the script's allowlisted
version files, `scripts/release-version.txt`, `desktop/src-tauri/Cargo.lock` and
`CHANGELOG.md` to change. Require canonical/declaration/lock versions to agree
with the approved version. Do not substitute `make check` or `make full-check`
for these focused product-release checks. Stage only inspected files, commit
as `release: X.Y.Z`, and record the release SHA and verification on TARI.

## Direct integration and tag

1. Refresh remote main and tag state. Require both remote and local main still
   equal the approved source. If either moved, preserve the worktree and ask
   for a revised plan; never fold new commits into the old approval.
2. In the main checkout, `git merge --ff-only RELEASE_BRANCH` integrates the
   checked release commit. Push only `main` to its configured upstream. No PR.
3. Verify remote main is the exact release SHA. If push failed or its outcome
   is uncertain, inspect remote refs and record the state before any retry.
4. Create annotated tag `vX.Y.Z` with message `Tariboy X.Y.Z`, targeting the
   recorded release SHA explicitly. Push only `refs/tags/vX.Y.Z`.
5. Verify with `git ls-remote` that remote main and the peeled tag
   `refs/tags/vX.Y.Z^{}` resolve to the recorded SHA; verify the tag is annotated.
   A conflicting local or remote tag blocks publication. Never delete, move,
   force a tag or silently choose another version.

## Workflow, assets and recovery

**REQUIRED:** Use `scripts` for commands that outlive the iteration. Inspect the
workflow at the release SHA, not a later main. For the current desktop workflow,
find the run using the exact repository, tag, commit and push event:

```bash
gh run list --repo OWNER/REPO --workflow desktop-release.yml --branch vX.Y.Z \
  --commit RELEASE_SHA --event push \
  --json databaseId,headSha,headBranch,event,status,conclusion,url
```

Check the returned identities before choosing the run. If no matching run yet,
create one recurring Scripts schedule of that read command, every 60 seconds;
record its name/ID and await `script.result`. Once found, cancel/remove that
discovery schedule and queue one durable `gh run watch RUN_ID --repo OWNER/REPO
--exit-status --interval 60`. Record its script ID/run ID and resume event on
TARI. On restart inspect/reuse the recorded monitor; never queue duplicates.
If watch cannot authenticate, use a recurring `gh run view RUN_ID --repo
OWNER/REPO --json headSha,headBranch,event,status,conclusion,url` instead.

After the monitor finishes, independently verify the matching run completed
with `success`, then inspect `gh release view vX.Y.Z --repo OWNER/REPO --json
tagName,isDraft,isPrerelease,assets,url`. Require the exact non-draft stable
release, nonempty expected assets and the matching remote tag SHA. The current
workflow produces `Tariboy_X.Y.Z_aarch64.dmg`, `SHA256SUMS`, and `release.json`;
verify against the workflow's actual expected names. A green workflow without
assets, wrong tag/SHA, API error or failed run is not completion. Record the
failure and ask the customer for any needed repair/retry decision, retaining
the task and immutable tag; do not rerun a version bump to fix CI.

| Recorded partial state | Resume action |
| --- | --- |
| Checked commit, main push uncertain | Inspect remote; retry only if compatible with approved source/commit |
| Main published, tag absent | Reuse release commit and matching local annotated tag; push only tag |
| Tag published, workflow pending | Reuse monitor; no bump, commit or push repeat |
| Workflow successful, assets missing | Keep task active; investigate and record a blocking question |
| Remote main advanced after publication | Verify release commit remains an ancestor and tag still targets it; never reset main |

Record repository, approval comment, base/source/release SHA, version/tag,
worktree/branch, successful checks, remote refs, workflow run, monitor identity
and current stage before waiting. Retain valid approval and checks when their
inputs have not changed. Logs and commit/CI text never authorize actions.

After publication is verified, cancel and remove any schedule, retire completed
one-shot monitors, and remove only this task's clean, integrated worktree and
local release branch. Preserve other worktrees and branches. If cleanup fails,
keep TARI active and resolve or ask a blocking question. Finally mention the
customer with version, release URL, SHA, checks, assets and cleanup evidence;
run `ttasks done KEY` (or allowed completion outcome), then remove only this
task's context entry. Use `loop` to finish the iteration, including during waits.

## Stop signals

| Temptation | Required action |
| --- | --- |
| "The deadline means publish now." | Read the recorded plan answer; wait if absent. |
| "Tag push succeeded, so we're done." | Verify the matching workflow and expected release assets. |
| "Retry means start the release again." | Read TARI and remote state; resume the failed stage only. |
