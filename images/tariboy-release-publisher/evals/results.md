# Final image observations

The authoritative observations are `final-cli-*.json`, separate from the
individual skill suite. All six runs use Codex CLI `gpt-5.6-terra`, `medium`,
read-only mode and simulated tools. Each case has two fresh calls carrying an
explicit transcript: select skills from the catalog, then receive the exact
requested bodies and propose actions. Raw requests, responses, selected skills,
guidance hashes and event traces are retained. This is a routing/decision
simulation, not an executed release or a persistent multi-turn agent session.

Candidate inputs are the complete static role and finishing prompt, the
manifest-derived catalog, and the exact bodies requested by the first call.
Runtime data is limited to the case fixture: missing identity/workdir can cause
an appropriate conditional stop. Baseline uses the minimal release role plus
publish-release/tasks/scripts catalog; requested bodies are supplied too.

| Case | Baseline | Candidate |
| --- | --- | --- |
| fresh-release | Requests tasks/release skill, but leaves queue unspecified | Requests tasks/release skill and runtime helpers; proposes one TARI root, Goal and recorded customer plan approval before mutation. |
| approved-release | Worktree/main process is inconsistent and closes after tag refs | Reuses TARI-7/approval; requests missing workdir if not on the task; proposes synchronized main, separate worktree, script, changelog, direct integration, durable monitor and verified assets before cleanup/closure. |
| resume-pending | Requests tasks/scripts and retains wait | Requests release/tasks/scripts/context/loop; reuses healthy schedule-77, keeps TARI-7 active, no repeated bump/push/tag/monitor setup. |

The monitor fixture explicitly identifies an existing healthy `gh run view`
schedule. Earlier ambiguous discovery-vs-watch observations are retained in
`prior-cli/`, `prior-r3/` and `image-behavior.md`. Condensed coordinator summaries
are exploratory and do not substitute for the final raw JSON records.

An earlier candidate unnecessarily claimed workflow work while resuming a
flexible task. The final role and skill explicitly distinguish those APIs.
The final candidate avoids that claim. These abbreviated responses are not
complete runnable scripts: some helper paths, check ordering and message
acknowledgement details remain unstated or schematic. No claim that every
rubric substep executed successfully is made. Root-agent review verifies the
observed decisions only; the host build and real integration remain separate.
