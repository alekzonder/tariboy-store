---
name: scripts
description: Use when a local command must continue beyond the current Tariboy iteration or run repeatedly on a durable schedule.
---

# Durable Scripts

This skill's `scripts/scripts.sh` launcher lives inside this skill directory
and calls the identity-bound daemon through `TARIBOY_TOOLS_SOCKET`.
Execute the launcher when command execution is available. If it is unavailable,
return the exact command instead; never claim a script was queued, scheduled,
rerun, cancelled, or removed unless the command succeeded.

Run once with `scripts/scripts.sh run <name> -- <command>`. Queue it exactly once,
finish the iteration, and consume the later `script.result` message instead of
waiting in the current iteration.

Run repeatedly with `scripts/scripts.sh schedule <name> --every <seconds> -- <command>`.
Runs never overlap. A run that exits with `$TARIBOY_QUIET_EXIT` (`111`)
publishes nothing and keeps the schedule; it is the only outcome that does.
The daemon exports the code to every run, so a shell command stays quiet with
`exit "${TARIBOY_QUIET_EXIT:-111}"` and a Python one with
`sys.exit(int(os.environ.get("TARIBOY_QUIET_EXIT", "111")))`.

Inspect with `scripts/scripts.sh ls`, `scripts/scripts.sh runs`, and
`scripts/scripts.sh logs`; use `scripts/scripts.sh rerun`,
`scripts/scripts.sh cancel`, or `scripts/scripts.sh rm` for lifecycle control.

## After `run` or `schedule`, do not wait in the iteration

**REQUIRED:** Queueing a definition ends your work on it in this iteration.
Do these two steps, then continue with other work or finish the iteration:

1. Record the `scr-...` script ID as the wait object, on the task or in the
   context entry.
2. Finish the iteration. The result arrives as a `script.result` message in
   the prompt of a later iteration.

New letters enter the prompt only at the start of an iteration. An agent that
waits inside the iteration never sees the `script.result` message, also when
the run was interrupted. So, after `run` or `schedule`:

- Do not poll the output file, the log, `scripts/scripts.sh runs`,
  `scripts/scripts.sh logs` or `scripts/scripts.sh ls` to see whether the run
  finished.
- Do not use `sleep`, `until`, `while`, `tail -f`, `watch`, a Monitor tool or
  any other background wait loop for the run or for its output.
- Do not make the next step of this iteration depend on the run's output.
  Read the output in the iteration that receives the `script.result` message.

One read of `ls` or `runs` to record the ID or to verify a saved command is
allowed. A request to get the output "now" or "in this iteration" does not
change this: queue the run, record the ID and say that the output is read after
the `script.result` message arrives.

## An interrupted one-off run

A `script.result` message with status `interrupted` for a one-off run (`mode`
`once`) means a daemon restart stopped the command at an unknown point. The
definition is `completed`. Handle it in this order:

1. Read `scripts/scripts.sh runs <script-id>` and `scripts/scripts.sh logs
   <run-id>` for what the run did, and read the command's source with a file
   read. Never execute the command to test it.
2. Decide whether a repeat is safe. A repeat is safe only when the command has
   no effect outside its own working files, or when its source shows it is
   idempotent or resumes from saved progress.
3. Safe: run `scripts/scripts.sh rerun <script-id>` with the `scr-...` ID of
   the message and record the same ID as the wait object. End your reply with
   this sentence, with the real ID: "Rerun `<script-id>`; the new result
   arrives as a `script.result` message in a later iteration." Then finish the
   iteration.
4. Not safe, or unknown: do not rerun and do not start a new run. The effect
   can be an email, a payment, a deploy, a write to a remote system or a
   deletion. Ask one question on the task with `ttasks ask`, mentioning the
   customer. Name the command, say what is unknown (what the interrupted run
   already did) and ask whether to repeat it. Set the task to `wait_customer`
   and finish the iteration.

Never run `scripts/scripts.sh run <name> -- <command>` again for the same work:
it creates a second definition. Repeating a command with an external effect
without the check above is forbidden.

## Address every definition by its script ID

**REQUIRED:** `rerun`, `cancel`, and `rm` accept only the `scr-...` script ID
or a `srun-...` run ID. Names are not unique and are not resolved: passing one
fails with `not found`, and `run <name> -- <command>` creates a second
definition instead of resuming the stopped one.

Take the ID from the `script_id` field of the `script.result` message that woke
you, from the creation output, or from `scripts/scripts.sh ls`. Record the
script ID, not only the name, wherever a durable monitor is recorded.

## A published result stops the schedule

A recurring definition keeps its schedule only while every run stays quiet.
The moment a run publishes a `script.result` message, the daemon sets the
definition to `completed` and clears its next run: the agent is notified once
instead of repeatedly, and **no further runs happen until it is resumed**.

This covers every published outcome:

| Event | Effect on the recurring definition |
| --- | --- |
| Run exits with `$TARIBOY_QUIET_EXIT` (`111`) | No message; schedule keeps running |
| Run exits with any other code, success or failure | Result published; definition stopped |
| A command that never exits with `$TARIBOY_QUIET_EXIT` | Every run publishes, so the schedule stops after the first run |
| `cancel <run-id>` for one active run | That run still publishes a result, so the definition stops too |
| A run interrupted by a daemon restart | Recovery publishes the interrupted result, so the definition stops |
| `cancel <script-id>` | Definition cancelled; it can never run again |

## Handling a `script.result` for a recurring definition

**REQUIRED:** Process the result, then close it with exactly one of these two
decisions before the iteration ends. Doing neither silently ends the
observation.

1. **Still needed** — resume the same definition:

   ```bash
   scripts/scripts.sh rerun <script-id>
   ```

   `rerun` runs it now and returns the definition to `active`, so its fixed
   delay continues afterwards. Never create a replacement schedule for work
   the stopped definition already describes.

2. **No longer needed** — remove it:

   ```bash
   scripts/scripts.sh rm <script-id>
   ```

   The published result already stopped it, so no `cancel` is needed. Run
   `scripts/scripts.sh cancel <script-id>` first only when `ls` still reports
   `state: active`.

### Stop one run, keep the schedule

`rerun` is the only command that resumes a stopped definition. No command
resumes it at the next interval instead: `rerun` always starts one run now,
and the fixed delay follows that run.

A request to stop the current run but keep the schedule is decision 1, so
the person has already given it. Complete it in one turn:

1. `scripts/scripts.sh cancel <run-id>` with the running `srun-...` ID.
2. `scripts/scripts.sh rerun <script-id>` with the definition's `scr-...` ID.
3. Reply with these three facts, in this order: the cancelled run published
   a result, and that result stopped the definition; `rerun` resumed it; one
   new run started now, and the fixed delay follows it.

A stopped definition is not a wait object. Never end an iteration describing a
definition that published its result as an active monitor: either it was
resumed with `rerun` in this iteration, or the iteration's wait object is
something else.

## External prerequisite failures

**REQUIRED:** A recurring schedule whose command cannot succeed until an
external prerequisite changes, such as a missing credential, binary, or
dependency, is no longer a valid wait object. Its failing result already
stopped it, so take branch 2 above and never `rerun` it:

```bash
scripts/scripts.sh rm <script-id>
```

Run `scripts/scripts.sh cancel <script-id>` before it only when `ls` still
reports `state: active`. Then, for a Native Task:

1. Mention the customer and ask one blocking question. Reuse a matching
   unanswered question instead of creating or repeating it.
2. Set the task to `wait_customer` if it is not already there and record the
   question as the only resume event.
3. As the final action, finish the iteration through the `loop` skill with
   `scripts/loop.sh done`.

The failure is handled only after the definition is removed, the task has one
customer-answer wait, and the iteration is finished. An action trace that omits
any of these is incomplete.

Pausing or disabling leaves the useless definition behind; it does not complete
this sequence. Do not rerun the command, create a replacement schedule, or
repeat the failure comment while the question remains unanswered.

## Red flags

| Thought | Reality |
| --- | --- |
| "The schedule keeps running, so I can just finish." | Any published result stopped it. Resume with `rerun <script-id>` or remove it. |
| "Cancelling one run leaves the schedule intact." | That run still publishes a result, which stops the definition. |
| "`rerun` starts a run now, so I will ask before resuming." | No command resumes later. A request to keep the schedule is the decision: `rerun <script-id>` and say one run starts now. |
| "I will schedule it again to resume monitoring." | A second definition duplicates the work. `rerun <script-id>` resumes the recorded one. |
| "`rerun <name>` is clearer than the ID." | Names are not resolved; only `scr-...` IDs work. |
| "I will wait for the output file in this iteration." | The `script.result` message cannot arrive until the next iteration. Record the ID and finish. |
| "A short `sleep` loop on the log is cheap." | It is the same wait. Do not poll `runs`, `logs` or files after `run`. |
| "The run was interrupted, so I run it again." | Check the effect first. `rerun <script-id>` only when a repeat is safe; otherwise `ttasks ask`. |
| "It succeeded, so nothing stopped." | Success is not quiet. Only `$TARIBOY_QUIET_EXIT` (`111`) is quiet. |
