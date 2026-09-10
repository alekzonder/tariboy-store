# Final skill observations

The authoritative runs are `full/final-cli-{baseline,candidate}-*.json`.
Each JSON preserves the complete request, exact response, guidance hashes,
model/effort, exit status and CLI event trace. Both sides of each pair used
Codex CLI, `gpt-5.6-terra`, `medium`, full guidance inline, no live tools.
The root agent reviewed these traces against `cases.json`; no statistical
success rate or executed-integration claim is made.

| Case | Baseline observation | Candidate observation |
| --- | --- | --- |
| approval | Publication authorization, without the required TARI workflow | Proposes TARI and a recorded Alice approval wait; minor 0.56.0. Repository is unspecified, so the complete plan remains conditional on inspection. |
| resume-tag | Completes after remote refs | Reuses task/commit/tag, pushes only missing tag, then waits on durable workflow discovery and assets. |
| main-moved | Stops on divergence | Preserves B, inspects the changed range, proposes 2.0.0 and asks TARI-8 for revised approval. |
| workflow-pending | Incomplete durable workflow/task treatment | Keeps task active, records monitor/run and verifies matching successful workflow plus named assets before completion. |
| missing-tag | Infers a baseline from canonical version | Rejects unrelated v9.0.0 and canonical-version guessing; asks for an explicit baseline/version plan. |
| breaking-changelog | No complete worktree/CHANGELOG publication process | Proposes 2.0.0, dated Removed entry, compare link and preserved history. Full synchronization/check execution is not observed in this abbreviated plan. |
| tag-conflict | Refuses conflicting tag replacement | Preserves C/X, refuses force/deletion/retagging, asks the recorded customer for a new decision. |

## Wording controls

`micro-cli-control-approval-1..5.json` are five fresh no-guidance controls.
The final candidate approval run plus `micro-cli-candidate-approval-2..5.json`
provide five fresh candidate observations with the same request, model,
effort, CLI and response-length setting. The control exhibits incomplete
Native Task handling and unsafe shortcuts; candidate observations explicitly
record a TARI question and stop before release mutation. They often ask first
for the missing repository identity: this validates intake waiting, not a
fully populated approval plan. Inspect the raw responses for individual
criterion evidence rather than treating a keyword count as a pass rate.

## Revisions and limits

Earlier runs are retained, not pooled into the final comparison:

- Source-skill/subagent pilot and condensed or mispaired coordinator runs.
- Candidate CLI mistakes: nonexistent `ttasks whoami`, whole structured output
  used as a scalar, source label B used as a customer login, and an unnecessary
  workflow assignment claim. The final skill explicitly addresses these.
- `prior-r3/` contains the immediately preceding CLI observations.

Some final responses still invent absolute helper locations or use schematic
placeholders. Command fidelity was **not executed or validated** by these
text-only simulations. Required data absent from a fixture also limits how
much of its later sequence is observable. Version/approval/recovery decisions
are useful evidence; they are not proof of live Git, task-client, monitoring
or artifact behavior. Packaging is verified separately by Store `make check`.

The subagent harness reached its thread limit; a CLI read-only probe could not
read a file in this environment. Final pairs therefore supply exact guidance
inline and prohibit tools. Image routing uses a separate two-stage simulated
READ protocol, documented in the image eval directory.
