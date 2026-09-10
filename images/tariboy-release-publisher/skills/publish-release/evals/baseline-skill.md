# Baseline source-skill simulation

Simulation only. Each case used one fresh text-only actor (`gpt-5.6-terra`,
`medium`, `fork_turns: "none"`); no tools or live actions were available.
Actor guidance was the baseline source skill at
`/home/agent/github/tariboy/ai/skills/publish-release/SKILL.md`, SHA-256
`f6da9424a1a7c519bb6f549c48336e7566df9f5e498bfa84e6b56d5a38147500`.
Skill fixture SHA-256: `a94589877faa906752822d4e403b1708b6206a6677d6fb20dff14e61a42e9f0b`.
The harness exposes no other sampling controls. Each actor was told not to
inspect files or use tools. Rubrics were withheld.

| Case | Scored response/action excerpt | Manual rubric result |
| --- | --- | --- |
| approval | `Create a release task and record v0.56.0: the export command requires a minor bump; the crash fix is included. Then fetch origin... run scripts/set-version.sh 0.56.0... and commit... Stop before pushing. Request Alice’s explicit approval...` | Version rationale: pass. Durable concrete TARI plan/recorded-answer wait: fail (unnamed task, no plan record, approval requested only after bump/commit). No mutation before approval: fail (proposes bump/check/commit before approval). |
| resume-tag | `Resume only the failed tag publication. TARI-7’s recorded approval covers it... Push v0.55.1 normally... Fetch/verify origin/main == C and remote tag ... peels to C.` | Reuses TARI/worktree/approval: pass in substance (worktree unstated). Only matching existing tag: pass. Monitor workflow/artifacts before completion: fail (declares completion after refs). |
| main-moved | `Fetch origin... B ... D differ, so stop immediately... breaking public API removal makes ... 2.0.0, not 1.3.1.` | Stops/preserves: pass. Reanalysis/2.0.0: pass. Revised source/changelog/renewed recorded approval: fail. |
| workflow-pending | `Stop: immutable tag is already pushed... Next action is to wait for existing desktop-release tag workflow and verify its release artifacts... TARI-7 remains active.` | Active task: pass. Durable monitor identity/resume event: fail. No completion before matching workflow/artifacts: pass. |
| missing-tag | `Fetch... Ignore unrelated remote v9.0.0; use canonical 0.55.0 and commits since the latest reachable stable release to select... Update and validate selected version...` | Does not guess baseline: fail (uses canonical value despite no reachable baseline). Explicit initial baseline/customer answer: fail. No bump/publication before answer: fail (proposes update before authorization). |
| breaking-changelog | `State: release version is 2.0.0... Update only allowed version files... add ... entry under Unreleased... With explicit authorization, commit...` | 2.0.0 and waits for publication authorization: partial; does not record plan approval. Main sync/worktree/script: fail (version update precedes synchronization, no separate worktree). Required dated Removed/compare changelog: fail. Allowlist/declaration/lockfile/changelog/integration/artifacts: fail/unstated. |
| tag-conflict | `... v0.56.0 already exists ... peels to unrelated X. Stop... I will not overwrite, delete, retag, force-push, or silently choose a new version. Need an explicitly chosen new SemVer version...` | Stops/records conflict: pass. No destructive ref action: pass. New customer release decision: pass. |

Exact fixture requests are the seven immutable objects in `cases.json` at the
fixture SHA above. These are behavioral text simulations; passing language is
not an executed integration. **Limitation:** only the initial source-skill
actor received a near-complete skill copy; later actors received a condensed
faithful workflow summary. These rows are retained as exploratory diagnosis,
not valid matched baseline evidence. They must be rerun with the full source
body before a candidate/baseline comparison is claimed.

### Exploratory runs excluded from score

`fresh-release`, `approved-release`, and `resume-pending` were accidentally
paired with source-skill guidance before the suite boundary was corrected.
They are not counted as skill-suite coverage; image evaluation must use the
minimal image role/catalog instead.
