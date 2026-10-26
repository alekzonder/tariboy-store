---
name: schedule
description: Use when an agent needs a one-shot or recurring future Tariboy wake-up or a scheduled letter to another principal.
---

# Agent Schedules

This skill's `scripts/schedule.sh` launcher lives inside this skill directory
and calls the identity-bound daemon through `TARIBOY_TOOLS_SOCKET`.
Execute the launcher when command execution is available. If it is unavailable,
return the exact command instead; never claim a schedule was added or cancelled
unless the command succeeded.

Schedules create future wake-ups or scheduled letters. They run no local
command. Each firing is a letter from `system:schedule`, a request unless the
payload says `notice`; without `--to` it goes to you and wakes you.

- One-shot: `scripts/schedule.sh add --kind oneshot --spec <time>`
- Recurring: `scripts/schedule.sh add --kind cron --spec "<cron expression>"`
- Inspect: `scripts/schedule.sh ls`
- Cancel: `scripts/schedule.sh cancel <id>`

Add `--to <principal>` (`agent:NAME`, `user:LOGIN`, `group:NAME` or
`plugin:NAME`) when the firing should send its letter to another principal
instead of waking you, and `--message <json>` to set the letter: an object
with optional `kind`, `subject`, `text`, `data` and `notice` fields. The
`--message` value must be valid JSON; anything else is a usage error.

`cancel` is the only removal action. There is no `rm`, no pause and no resume:
a cancelled schedule is gone, and a schedule needed again later is added anew.
Never invent another lifecycle subcommand for this launcher.

## Schedule or durable script

| The request needs | Owning skill |
| --- | --- |
| A wake-up at an absolute one-shot time or on a cron expression | `schedule` |
| A firing that sends a letter to another principal instead of waking the agent | `schedule` |
| A future wake-up with no local command to run | `schedule` |
| A local command that outlives the iteration, once or every N seconds | `scripts` |
| Run history, logs, `rerun` or `rm` | `scripts` |

**REQUIRED:** use `scripts` for every recurring local command, however short,
and `schedule` for every timing this launcher expresses. Durable scripts accept
only a fixed `--every <seconds>` interval and always require a command, so they
express neither an absolute one-shot time, nor a cron expression, nor a
scheduled letter. A request naming the other skill does not change this boundary:
state which skill owns the request and why.
