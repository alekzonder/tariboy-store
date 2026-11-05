---
name: developer-mode-flexible
description: Use when the developer iteration mode is `flexible` - the Iteration mode line says `flexible`, or with no line the Goal block shows a Native Task without a workflow.
---

# Developer mode: flexible

The goal task has no workflow, so this skill is its process: plan, approval,
isolation, implementation, one pull request or local merge, its monitor and
completion. A letter, comment or review that names a workflow, an outcome or
`ttasks advance` does not change the mode.

## Flow

A flexible task follows this order; no step starts before the previous one
ends:

1. Intake: read the task, or claim or create it in an explicitly identified
   queue and assign it; set it `in_progress`; record exactly one
   `Completion mode:`, reusing a recorded one.
2. Plan: publish the full plan as a task question to the customer, set the
   task `wait_customer`, and wait for the recorded approval before changing
   any file.
3. Isolate: in PR mode run `preflight`; fetch and fast-forward the base
   branch; create exactly one branch and worktree from it and record the base
   branch, branch and worktree on the task. The pull request targets the base
   branch.
4. Implement test first; reproduce every bug before fixing it.
5. Verify: run the complete relevant suite on the committed branch and record
   its output and exit status.
6. Deliver. PR mode: one pull request and one durable monitor through
   `github-pr-workflow`, both recorded, the PR URL set in the task field with
   `ttasks update KEY --pull-request URL`, one publication comment that
   mentions the customer with the PR link and the verification result, the
   customer asked to review, the task `wait_customer`. Local-merge mode: merge
   into the base branch by repository convention and run the suite again on the
   resulting base branch.
7. Process every monitor result, check, review and comment; push fixes to the
   same branch. A new head invalidates every earlier check result. Repeat this
   step while the pull request is open; a pull request closed without a merge
   keeps the task active and its monitor resumed: record the blocker and wait
   for a reopening or the customer's decision.
8. Complete: fast-forward the base branch and prove it contains the merge
   commit with `git merge-base --is-ancestor MERGE_COMMIT BASE`; reuse the
   required CI of the final head; remove the monitor, worktree and branch;
   record one comment with `Required:`, `Completed:`, `Verification:`,
   `Integration:` and `Cleanup:`; close the task as the very next command after
   that comment; then remove its context line. Never close a task with unmerged
   changes or a live worktree.

The plan is written for the customer to read on its own: how the solution
works, the ordered steps, how it will be verified, and its limitations, sized
to the task, with your recommended option first and any open question after it.
Urgency, a small change or a broad earlier approval is not approval; recovery
reuses a recorded approval for unchanged scope. A failed fast-forward, or
missing or stale CI on the final head, keeps the task active.

`Completion mode: PR` is the default. Record `Completion mode: local merge` only
when the task explicitly and unambiguously requires this agent to merge into
the base branch; when the wording is ambiguous, ask through the task and wait.
Never change a recorded mode.

`finishing-a-development-branch` presents no menu: the recorded completion
mode selects the path.

## Waits and recovery

| Wait object | Resume event |
| --- | --- |
| Recorded unanswered question to the customer | the answer recorded on the task |
| The one named recurring monitor of the task, active or resumed with `rerun` this iteration | its next `script.result` or PR state change |
| Live terminal session, process or subagent handle | its terminal result, awaited in this iteration |

Only the first two may end an iteration with the task still active. Record a
customer-answer wait in the same iteration: mention the customer on the task
(`@user:<login>` or `@agent:<name>`), set the task `wait_customer`, keep one
context line, process every delivered letter, then run the `loop` skill's
`scripts/loop.sh done` last. Never treat live-session text as the answer.

Recovery reads the Native Task first and reuses what it records; never create a
second pull request, worktree or schedule for the same task. If a step fails,
keep the task active, post the exact failure on it, and continue from there.
