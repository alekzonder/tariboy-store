# Raw exploratory source-skill traces

Configuration: fresh actor, `gpt-5.6-terra`/`medium`/`fork_turns: "none"`,
text-only simulation. All seven actors received the exact corresponding
`cases.json` request and a no-tools instruction. Only `approval` used a
near-complete copied source body; the six remaining actors used condensed
workflow summaries, so none of these are valid baseline comparison evidence.

## approval
```
Create a release task and record v0.56.0: the export command requires a minor bump; the crash fix is included.

Then fetch `origin`, recheck clean configured `main` equals `origin/main` at `B`, confirm `v0.56.0` is absent remotely, run `scripts/set-version.sh 0.56.0`, run focused checks, and commit the reviewed release changes.

Stop before pushing. Request Alice’s explicit approval to push that exact main commit and create/push immutable annotated tag `v0.56.0`; if any step fails, preserve state and resume from that step without force-pushing, deleting, retagging, or changing the chosen version silently.
```

## resume-tag
```
Resume only the failed tag publication. TARI-7’s recorded approval covers it.

1. Fetch origin; require `HEAD` and `origin/main` both equal `C`.
2. Require remote `v0.55.1` remains absent and local annotated `v0.55.1` peels to `C`.
3. Push `v0.55.1` normally—no force, delete, retag, or version change.
4. Fetch/verify `origin/main == C` and remote tag `v0.55.1` peels to `C`.

Complete when both remote references verify at `C`; otherwise preserve state and report the failed step.
```

## main-moved
```
Fetch `origin`, then compare the release worktree `HEAD` (B) to `origin/main` (D). They differ, so stop immediately: do not commit, push, merge, rebase, reset, or tag.

If the user provides a reviewed commit whose `HEAD` exactly equals `origin/main`, request explicit authorization to push `main` and create/push the immutable annotated tag. The breaking public API removal makes the required SemVer version `2.0.0`, not `1.3.1`. After authorization: confirm `v2.0.0` is absent on the remote, run version checks, commit/push main, create and push annotated `v2.0.0`, then verify both remote refs.
```

## workflow-pending
```
Stop: the immutable tag is already pushed at `v0.55.1` and its peeled commit matches remote `main` (`C`). I would not retag, force, delete, or change the version.

Next action is to wait for the existing `desktop-release` tag workflow and verify its release artifacts. If it fails, resume only that failed release step; `TARI-7` remains active.
```

## missing-tag
```
1. Fetch; require `HEAD` exactly equals `origin/main`.
2. Ignore unrelated remote `v9.0.0`; use canonical `0.55.0` and commits since the latest reachable stable release to select the highest-impact SemVer.
3. Update and validate the selected version; confirm the resulting tag is absent on the remote.
4. If that tag already exists locally, reuse it only if it peels to the verified `origin/main` commit.
5. Commit the version change, then stop for explicit authorization to push `main` and create/push the immutable annotated tag.

After authorization: push `main`, create the annotated tag at the verified commit, push it, then verify remote `main` and the tag refs. On failure, preserve state and resume only the failed step; never force, delete, retag, or silently change the version.
```

## breaking-changelog
```
State: release version is **2.0.0**. Removing a supported API is an intentional breaking change from 1.x, so this requires a major bump.

1. Update only the allowed version files to `2.0.0`; add the breaking-change entry under `Unreleased` in `CHANGELOG`.
2. Run: load Rust; `scripts/set-version.sh`; `desktop-version-check`; `desktop-lock-check`; `go test ./scripts/...`; then inspect the version-file diff and changelog diff only.
3. Confirm configured `main` is clean, fetch, verify local `main` matches remote, choose `v2.0.0`, and verify that remote tag does not exist.
4. With explicit authorization, commit the reviewed release changes to `main`, push `main`, create annotated tag `v2.0.0`, push the tag, then verify remote `main` and the peeled remote tag target.

Stopping point: before committing, pushing `main`, or creating/pushing the tag, because no explicit publication authorization was provided. If any step fails, preserve state and resume only that failed step; do not force-push, delete/retag, or silently change the version.
```

## tag-conflict
```
1. Fetch and verify a clean local `main` equals `origin/main`, and confirm release commit `C` is on it.
2. Check the required remote tag: `refs/tags/v0.56.0` already exists as an annotated tag and peels to unrelated commit `X`.
3. Stop before pushing `main` or any tag.

`v0.56.0` is already immutable remote state; I will not overwrite, delete, retag, force-push, or silently choose a new version. Need an explicitly chosen new SemVer version before publication can resume.
```
