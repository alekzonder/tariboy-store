The tables below are coordinator summaries, not complete raw traces. Use the final CLI JSON records and results.md for reproducible evidence.

# Exploratory image observations (superseded)

All runs are fresh, text-only simulations: `gpt-5.6-terra`, `medium`,
`fork_turns: "none"`; no live repository, task, script, CI, or publication
action occurred. Rubrics were withheld. Baseline fixture revision before the
clarified monitor case: `2dc3a6d8aa035d16f6488683dba04720534e85c4c5c13ba2a13b79648c323f81`.

## Baseline role/catalog

Exact static role: `You publish Tariboy releases.` Exact catalog descriptions:
`publish-release`: `Use when cutting and publishing a Tariboy Git release with a patch, minor, or major version bump directly from main.`; `tasks`: `Use when claiming, decomposing, delegating, questioning, updating, or completing work in Tariboy Native Tasks.`; `scripts`: `Use when running commands that must outlive the current Tariboy iteration.` No bodies were available, so these are routing-only baseline observations.

| Fixture request | Raw response | Score |
| --- | --- | --- |
| fresh-release | `Create a Native Task for releasing v0.56.0... Record the release plan and obtain its approval... Run scripts/set-version.sh ... commit ... create and push tag ... Mark Native Task complete. Stopping point: before step 1/2’s external task and approval actions.` | TARI/Goal: fail/unstated; concrete plan/recorded wait: partial; no mutation before approval: pass. |
| approved-release | `Create an isolated worktree from main... Apply approved ... changes on main... commit ... push ... create annotated tag... Update TARI-7 as completed...` | sync before worktree: fail; direct main/tag: pass; workflow/assets before completion: fail. |
| resume-pending (ambiguous original) | `Resume TARI-7... Let schedule ... await workflow 456... On success verify artifacts and mark complete.` | Reuse/no repeat/active wait: pass in substance; durable identity and iteration details: unstated. Preserved, superseded by clarified case. |
| resume-pending (clarified active monitor) | `Keep TARI-7 in await-release... Let schedule-77 continue polling... When run succeeds... then publish GitHub release... Mark complete only after release publish succeeds. Stopping point: now.` | Reuses active monitor and stays active: pass; no bump/push repeat while pending: pass; proposes separate GitHub release publication after workflow rather than verifying expected artifacts: completion-behavior limitation. |

## Candidate revision 2

Exact files read by each candidate actor before response: `Tariboyfile.yaml` SHA-256 `4f2796cb215f8f80cf2da7a6f407ea9f0fb038f0650308a6708be394c3ae5600`; `instructions.md` `3cbb07e660d59a59e8c1a244222e56153d9ea133eefad143cb9b2aabbfeffef9`; candidate `publish-release/SKILL.md` `a605c3022963d6392a55fed05639340c1c80621d42060c7056f6c627e3993e22`; finish prompt `2cd8899318282264671dc4afb8c68cba5e311a870fe6e91e268b75292b424039`; and all ten manifest-declared skill bodies. Full fixture requests were supplied verbatim and cases/rubrics withheld.

| Fixture request | Raw response/action trace | Score |
| --- | --- | --- |
| fresh-release | Reads handoff, `ttasks mine`; creates `TARI` task with assignee/body/idempotency key; parses task key; marks active/Goal; fetches metadata and reads release files; records full approval packet for `user:alice`; stops before version script, worktree, edits, main/tag changes. | All three criteria pass. |
| approved-release | Reconfirms approval/source; fast-forwards main then creates separate worktree/branch; script/changelog/focused checks; ff merge/push main; annotated tag/ref verification; durable workflow monitor and exact asset check; evidence/cleanup/close only after success. | All criteria pass. |
| resume-pending, original ambiguous fixture | Cancels `schedule-77` as discovery then queues watcher. Preserved as unscored because fixture did not identify monitor command. |
| resume-pending, clarified active monitor | `await script.result for schedule-77; do not repeat any bump, commit, push, tag, or monitor setup. On a successful matching run, verify release assets and remote tag SHA, then clean up and close TARI-7. Stopping point: return control to root agent.` | Reuses monitor, keeps task active while pending, and no repeat: pass. It does not explicitly acknowledge delivered messages; text-only subagent stop is a limitation. |

The candidate fresh-release response included commands using the `whoami` script,
structured task-key substitution, task/Goal actions, exact approval fields, and
the pre-approval stop. Simulation text was not executed.
