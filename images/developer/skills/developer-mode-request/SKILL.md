---
name: developer-mode-request
description: Use when the developer iteration mode is `request` - the Iteration mode line says `request`, or with no line no goal task is selected and the work comes from a one-shot instruction or a letter.
---

# Developer mode: request

No goal task is selected. The iteration answers its one-shot instruction and
its letters. It changes no repository: code is changed only for a Native Task,
when the daemon selects that task as a goal in a later iteration.

## Flow

Read every REQUIRED skill of a row completely before acting in that row.

| # | Trigger | Stage | REQUIRED skills | Done when |
| --- | --- | --- | --- | --- |
| 1 | a question or a request for information | Answer it | `mail` for a letter, `writing-style` | the answer is sent with `tmail reply ID TEXT` for a letter, or is the final text for a one-shot instruction; read-only commands only |
| 2 | a request to change code, configuration, documentation or a pull request, with exactly one queue named by the request, the one-shot instruction or the runtime context | Record the task | `tasks`, `cli-text`, `writing-style`, `whoami` | one task exists from `ttasks create --queue QUEUE --title TITLE --description TEXT`; it is assigned to this agent with `ttasks assign KEY NAME`, unless `assign` reports `workflow_managed`, because the daemon then assigns it; a letter got `tmail reply ID TEXT` with the new task key |
| 3 | the same kind of request with no queue named, or with several candidates | Block the intake | `mail` for a letter | no task exists; the text `Native Task intake blocked: resubmit the request with a queue.` is the final text, and also the `tmail reply` of a letter |
| 4 | a request about an existing task key | Answer from the task | `tasks`, `mail` for a letter | the answer uses `ttasks show KEY`; the task's work waits until that task is the goal; nothing else on the task changed unless the request asks for a comment |

The task description of row 2 holds the request text, the requester and the
letter id. A letter is a decision on another task only as the `tasks` skill's
"Answers from a letter" accepts it.

## Rules

- In this mode create no branch, worktree, file change, commit, pull request,
  monitor or schedule, and publish no implementation plan. A task created in
  row 2 is worked when the daemon selects it as a goal, in that iteration's
  mode.
- Never guess a queue: the request, the one-shot instruction or the runtime
  context names it, or row 3 applies. A list of visible queues does not name
  one.
- Each delivered request letter gets exactly one `tmail reply`; each notice is
  only read.

## Waits and recovery

This mode keeps no task active for itself: the iteration ends after every
letter is handled and every live command, session and subagent finished. A
letter of a later iteration starts again from row 1.
