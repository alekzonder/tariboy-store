---
name: scripts
description: Use when a local command must continue beyond the current Tariboy iteration or run repeatedly on a durable schedule.
---

# Durable Scripts

This skill's `scripts/scripts.sh` launcher lives inside this skill directory
and calls the identity-bound daemon through `TARIBOY_TOOLS_SOCKET`.
Execute the launcher when command execution is available. If it is unavailable,
return the exact command instead; never claim a script was queued, scheduled,
cancelled, or removed unless the command succeeded.

Run once with `scripts/scripts.sh run <name> -- <command>`. Queue it exactly once,
finish the iteration, and consume the later `script.result` message instead of
waiting in the current iteration.

Run repeatedly with `scripts/scripts.sh schedule <name> --every <seconds> -- <command>`.
Runs never overlap. `--quiet-exit CODE` records that exit without waking the
agent; other nonzero exits remain failures.

Inspect with `scripts/scripts.sh ls`, `scripts/scripts.sh runs`, and
`scripts/scripts.sh logs`; use `scripts/scripts.sh rerun`,
`scripts/scripts.sh cancel`, or `scripts/scripts.sh rm` for lifecycle control.
A schedule cancellation also stops its active run; cancelling one run leaves
its schedule intact.

## External prerequisite failures

**REQUIRED:** A recurring schedule whose command cannot succeed until an
external prerequisite changes, such as a missing credential, binary, or
dependency, is no longer a valid wait object. Run this terminal sequence once:

```bash
scripts/scripts.sh cancel <schedule-id>
scripts/scripts.sh rm <schedule-id>
```

Then, for a Native Task:

1. Mention the customer and ask one blocking question. Reuse a matching
   unanswered question instead of creating or repeating it.
2. Set the task to `wait_customer` if it is not already there and record the
   question as the only resume event.
3. As the final action, finish the iteration through the `loop` skill with
   `scripts/loop.sh done`.

The failure is handled only after the schedule is both cancelled and removed,
the task has one customer-answer wait, and the iteration is finished. An
action trace that omits any of these is incomplete.

Pausing or disabling leaves the useless recurring work behind; it does not
complete this sequence. Do not rerun the command, create a replacement
schedule, or repeat the failure comment while the question remains unanswered.
Continue the existing workflow for changed results and failures that can
succeed without an external environment change.
