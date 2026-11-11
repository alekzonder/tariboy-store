---
name: image-creator-mode-flexible
description: Use when the image creator iteration mode is `flexible` - the Iteration mode line says `flexible`, or with no line the Goal block shows a selected task that follows no workflow, such as a task of the TASK queue.
---

# Image creator mode: flexible

The goal task has no workflow, so this skill sets the process: plan, approval,
isolation, change and evaluation, one pull request with its monitor, and
completion. The review cycle (row R of `instructions.md`) is not part of it.

## Flow

Read every REQUIRED skill of a row completely before acting in that row. The
table names them; it does not replace them.

| # | Trigger | Stage | REQUIRED skills | Done when |
| --- | --- | --- | --- | --- |
| 1 | iteration starts with a selected or supplied task | Intake | `using-superpowers`, `tariboy-image-delivery`, `tasks`, `goal`, `context`, `mail`, `workdir` | the task, its customer and its recorded branch, worktree, PR and monitor are read; with no key, the matching task is claimed or created in an explicitly identified queue |
| 2 | no recorded approval covers the current scope | Investigate and agree | `tariboy-image-authoring`, `tariboy-workflow-authoring` when applicable, `tasks`, `brainstorming`, `writing-plans`, `writing-style` | a concrete plan — which image, workflow and skills change, why, eval coverage, delivery destination — is published as a task question to its customer, and the flexible task is `wait_customer` |
| 3 | approval for this exact scope is recorded on the task | Isolate | `tariboy-image-delivery`, `github-pr-workflow` when applicable, `using-git-worktrees` | `Completion mode` and its source are recorded on the task; in `PR` mode GitHub preflight passed, the base is fetched and fast-forwarded, and one task branch and worktree exist and are recorded; in `Customer VCS` mode isolation follows the customer's recorded explanation; a recovered task reuses the recorded one; without GitHub or that explanation the customer is asked with `ttasks ask` and the flexible task is `wait_customer` |
| 4 | the recorded workspace exists | Change and evaluate | `writing-skills`, `authoring-evals`, `tariboy-image-authoring`, `tariboy-workflow-authoring` when applicable, `image-creator`, `verification-before-completion` | missing evals created in the `evals/evals.json` source contract, baseline observed, the approved change made and the same scenarios rerun with a pinned model; generated run evidence kept in the workdir, not in committed `evals/`; skill and image evidence kept separate; `image_version` bumped for every image whose own directory or consumed local skill source changed; `workflow_version` bumped for every changed `workflows/NAME/`; packaging validated separately from behavior |
| 5 | the verified change is committed on the task branch | Deliver | `tariboy-image-delivery`, `github-pr-workflow` when applicable, `scripts`, `tasks`, `verification-before-completion`, `writing-style` | `PR` mode: exactly one PR and one durable monitor exist with their identifiers on the task, one comment mentions the customer with the PR link, verification results and an invitation to review, and the flexible task is `wait_customer`. `Customer VCS` mode: the pull request or review request the customer's explanation describes is created and recorded on the task; exactly one closure monitor from the poll source `tariboy-image-delivery` names is active, its saved command checked with `scripts/scripts.sh ls`, with its identifiers on the task, or with no such source none exists and the question also asks for that interface; the customer is asked with `ttasks ask` and the flexible task is `wait_customer`. In every mode the base is unchanged |
| 6 | a monitor result, check or review arrives | Process result | `tariboy-image-delivery`, `scripts`, `github-pr-workflow` when applicable, `systematic-debugging`, `receiving-code-review`, `verification-before-completion` | the PR or review request is re-read authoritatively; every changed or error result is handled and any fix is verified and pushed to the same branch; a new head invalidates all prior check success; the definition is resumed with `rerun`, or removed with one blocking question when an external credential, tool or dependency is missing |
| 7 | the closure monitor observes a merge with merge-commit metadata and an authoritative re-read confirms it | Complete | `tariboy-image-delivery`, `scripts`, `github-pr-workflow` when applicable, `image-creator`, `tariboy-workflow-authoring` when applicable, `verification-before-completion`, `tasks`, `context`, `writing-style` | the schedule is removed (cancelled first only while active), the base is fast-forwarded, post-merge checks pass, every image the merge affected is built from a workdir copy under both its `image_version` tag and `latest` with one matching digest, each merged workflow is recorded as an operator hand-over and never built, worktree and branch are removed, one consolidated comment records Required, Completed, Verification, Integration, Publication and Cleanup, `ttasks done KEY` ran, and the context entry is gone |

Rows 2 and 3 never swap: deadline, authority, sunk work and broad approval are
not approval, and task size scales plan detail, not the approval requirement.
Only a change that fits the rule `Change without approval` in `instructions.md`
skips row 2.
Row 6 repeats for as long as the PR or review request is open, including after
a close without merge, which keeps the same request, task and monitor active
and is never an integration. A published `script.result` stops the monitor
definition, so every row 6 pass ends by resuming the recorded `scr-...` script
ID with `scripts/scripts.sh rerun`, and row 7 removes it with
`scripts/scripts.sh rm` instead. A customer answer and a closure event are
independent: a review question never replaces the monitor, and row 7 never
waits for an answer.

Publication in row 7 is the only build that publishes: a `make check` or
validate build is a packaging fact. It selects images from the merge's changed
paths, the local skill sources their `skills-lock.json` files record and the
`extends` chains that reach a selected image, so a shared `skills/NAME` change
publishes every consuming image and a parent change every descendant. A build
error, a digest mismatch between the two tags, or a missing version bump keeps
the task active and blocks `ttasks done`. An image whose bump is missing is not
built or published under any tag, `latest` included; its fix is a follow-up
change asked through the task, never a bump or commit made after the merge.

Rows 3 to 7 change every file with Read, Edit and Write, also when a rebase
conflict stops the branch and also when one change repeats in many files.
Resolve each conflicted file with Read and Edit (or Write), one file at a time,
and make a repeated change as one Edit per file. No inline script writes a file.

Never run `ttasks advance` in this mode, and never use a workflow status
instruction: the task has no workflow. A task that does follow a workflow is
mode `workflow`.

## Waits and recovery

Continue every executable next action immediately. Only two things may end an
iteration with the task still active: a recorded unanswered task question, or an
active durable monitor. Read authoritative state once before waiting; never poll.

| Wait object | Resume event |
| --- | --- |
| Recorded question to the customer (row 2, or a decision asked in rows 5–6) | the answer recorded on the task |
| Named recurring closure monitor for the one PR or review request (row 5), active or resumed with `rerun` this iteration | its next `script.result` or PR or review state change |

The review cycle is not a wait object of any task: it keeps no task active
and never replaces a question or a closure monitor.

A customer-answer wait is completed in the same iteration that records it:
mention the customer on the task, set the flexible task to `wait_customer`, keep
the question and one `TASK-KEY next-action-slug` line in context, process every
delivered letter, and after all live commands, evaluators and subagents finish,
run `scripts/loop.sh done` as the exact final action. Never wait for an answer in
the live session.

When a recorded question is still unanswered, the flexible task must already be
`wait_customer` with the customer mentioned; if a recovered task is not, record
that transition in this iteration before finishing, however old the question is.
A live-session message is never the answer and never a reason to skip it; a
delivered letter is one only as the `tasks` skill accepts it.

While a recorded PR or review request is open and its poll source exists, the
closure monitor must be active before the iteration ends, even when a question
is also open.

Recovery reads the task first and reuses what it records — customer, approval,
branch, worktree, PR or review request, schedule and state directory: an
active definition is reused, a stopped one resumed with `rerun`, and a missing
one replaced by exactly one new schedule. Reuse a recorded approval
only while its scope still matches; otherwise ask again. Verification stays valid
while its inputs are unchanged.
