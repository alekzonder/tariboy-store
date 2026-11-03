---
name: iteration-review
description: Use when the user prompt has or lost a `## Review cycle` configuration, when an iteration starts on the agent's own loop schedule in review mode, when a `review-cycle` script or its letter is left from an older version, or when assessing other agents' finished iterations or done tasks with `tariboy assessment add`.
---

# Iteration Review

The review cycle assesses the finished iterations of the configured agents,
and their tasks after `done`, by rubric `iteration-review/1`, and writes each
assessment to the daemon. The daemon starts the cycle: an iteration that the
agent's own loop schedule starts runs one cycle, before any goal work of that
iteration. The skill creates no schedule, script or wake-up of its own, so a
failed iteration stops nothing: the next occurrence of the loop schedule
starts the next cycle. It changes nothing it assesses.

`REVIEW` below is `python3 SKILL_DIR/scripts/review.py`, with the absolute
path of this skill's directory. `WORKDIR` is the configured workdir.
`ASSESSOR` is this agent's own name (`$TARIBOY_AGENT`, see `whoami`): the
daemon records every assessment under it.

## Configuration

The cycle runs only from this block of the user prompt. Without the block, or
with `review_mode: off`, review mode is off.

```markdown
## Review cycle

review_mode: on
agents: AGENT, AGENT, ...
since: RFC 3339 time — the date the cycle was enabled
cycle_task: TASK-KEY
model: haiku
sample_size: 50
```

- `sample_size` is the most iterations one cycle assesses. Without the line
  it is 50. `SIZE` below is its value.
- `budget_usd: USD` is an optional line. Without it the cycle has no dollar
  limit: `sample_size` alone bounds what the cycle assesses. With it, step
  3.1 stops the cycle at that cost.
- The block sets no interval. An `interval_hours` line from an older version
  is ignored: the operator sets how often cycles run, see "Operator setup".

## Which step applies

First read the trigger of this iteration:

```bash
tariboy iteration inspect "$TARIBOY_AGENT" "$TARIBOY_ITERATION" --json
```

| Observed | Step |
| --- | --- |
| The configuration is present, `on` or `off` | "Remove the old schedule" first, then the row below that applies |
| Review mode on, `trigger` is `schedule` or `manual` | "Run the cycle", then the letters and the goal of the iteration |
| Review mode on, any other `trigger`, such as `message` | No cycle in this iteration; continue the normal Flow |
| Review mode off, `trigger` is `schedule`, no letters, no goal | No cycle; end the iteration with `scripts/loop.sh done --idle` |
| A `script.result` letter of `review-cycle`, with or without the configuration | "Remove the old schedule", reply to the letter, no cycle from this letter |

A cycle that found nothing to assess is still a cycle: it posts the cycle
comment and ends with plain `scripts/loop.sh done`.

## Remove the old schedule

Versions up to 0.18.0 of this image ran the cycle from a `review-cycle`
script with `review.py tick`. That script and its letters are not used now.

1. Run `scripts/scripts.sh ls`. If a definition named `review-cycle` exists,
   run `scripts/scripts.sh cancel SCRIPT_ID` only while it is `active`, then
   `scripts/scripts.sh rm SCRIPT_ID`. Never `rerun` it and never create a
   new one.
2. Remove its old state directory: `rm -rf "$WORKDIR/review-cycle"`.
3. Reply to a delivered `review-cycle` letter that the definition is removed
   and that the agent's loop schedule now starts the cycle.

## Operator setup

The operator, not the agent, sets how often a cycle runs, with the loop
schedule of the reviewing agent (`AGENT`). The agent never changes its own
loop.

| Goal | Command |
| --- | --- |
| A cycle every 3 hours | `tariboy loop schedule AGENT --value 'RRULE:FREQ=HOURLY;INTERVAL=3'` |
| No idle wake-ups between cycles | `tariboy loop interval AGENT --value 0` |
| Stop the cycles | set `review_mode: off`, then `tariboy loop schedule AGENT --clear` |

An occurrence never starts a second iteration while one runs, and the daemon
does not replay missed occurrences. Iterations that a missed cycle did not
assess stay candidates while they ended within the last 24 hours.

## Run the cycle

Do the cycle first in the iteration, before any goal work, so that its cost
holds only cycle work.

1. Set `START` to the current UTC time and `DIR="$WORKDIR/review/START"`.
2. `REVIEW candidates --dir "$DIR" --agents AGENTS --since SINCE --assessor ASSESSOR --size SIZE`
   selects the cycle's iterations and orders them:
   - only finished iterations that ended in the last 24 hours; an older
     iteration that no cycle took is skipped for good;
   - an idle iteration (`loop.sh done --idle`) is not taken and is not a
     problem;
   - an iteration with an assessment from this assessor is processed: it is
     not taken again, and it is never tagged;
   - problem iterations come first, newest first. A problem is an end
     without `loop.sh done` (`harness_error`, `timeout`, `no_i_am_done`), a
     refused check or a question to the customer;
   - then the others, round by round over the pairs agent × image version,
     newest first inside a pair. There is no quota per pair;
   - the selection stops at `SIZE` iterations. What is left stays a
     candidate of the next cycle while it is inside the 24 hours.
3. Repeat while candidates remain:
   1. Without `budget_usd`, `N` is 10. With `budget_usd`,
      `REVIEW cost --agent ASSESSOR --since START` gives `spent`, and
      `N = floor((budget_usd - spent) / 0.08)`, at most 10. When `N` is 0,
      stop: the rest of the selection is not assessed.
   2. `REVIEW pack --dir "$DIR" --limit N` writes one evidence pack for each
      of the next `N` candidates and prints `pack` and `out` paths.
   3. Start one subagent on the configured `model` with the assessor prompt
      below. Wait for it.
   4. `REVIEW validate --dir "$DIR"`. Delete each invalid output file; its
      iteration stays a candidate for the next cycle.
   5. `REVIEW add --dir "$DIR"` writes each valid assessment with
      `tariboy assessment add --file PATH`. It writes an assessment once:
      it skips a file this cycle already wrote, and an assessment that this
      assessor already has for the same iteration (or whole task) and
      rubric, and lists those under `skipped`. Count only `written`.

   Without `budget_usd`, the loop takes every candidate: 50 candidates are
   5 batches of 10, 14 are a batch of 10 and a batch of 4. When you report
   the commands of the iteration, give steps 3.2–3.5 once for each batch,
   with its `--limit`, and add up the `written` and `failed` counts of all
   `add` outputs for the comment.
4. Assess the tasks. Do this step even when no iteration was left to
   assess in step 3:
   1. `REVIEW tasks --dir "$DIR" --assessor ASSESSOR` writes a task pack
      (`# Task pack KEY`) for each `done` task whose iterations are all
      assessed and that has no task assessment, and prints `pack` and `out`
      paths.
   2. For each printed pack, start the same assessor subagent with the
      same prompt and the pair `PACK_PATH -> OUT_PATH`, inside the same
      budget check as step 3.1.
   3. The output is a task assessment: it has `task_key` and no
      `iteration_id`. `REVIEW validate --dir "$DIR"`, then
      `REVIEW add --dir "$DIR"`, which runs
      `tariboy assessment add --file OUT_PATH` for it.
   4. Count it in the comment as a task assessment, not as an iteration.
5. `REVIEW cost --agent ASSESSOR --since START` gives the cycle cost, and
   `REVIEW coverage --agents AGENTS --since SINCE --assessor ASSESSOR`
   gives the window figures. Post one comment on `cycle_task` with this
   command (`cli-text` quoted heredoc). Put the real value in place of
   every placeholder, `0` included, and keep every line:
   - `ITERATIONS`, `ASSESSED`, `PAIRS` and `PAIRS_ASSESSED` are the
     `coverage` fields `iterations`, `assessed_iterations`, `active_pairs`
     and `pairs_with_assessment`;
   - `LEFT` is `skipped.over_sample` and `SIZE` is `sample_size` of step 2;
   - `N` counts this cycle from the `add` outputs; `FROM`, `TO`, `KEY`,
     `X` and `Y` are as named in the line.

   Without `budget_usd`, write
   `Candidates not assessed (budget): 0` and
   `Cycle cost: X USD, no budget_usd`.
   When you report the commands of the iteration, show this command with the
   whole filled body, never only `"$BODY"`. A line you leave out or write as
   "see above" is a defect:

   ```bash
   BODY=$(cat <<'CYCLE_EOF'
   ## Review cycle START

   - Window: FROM – TO
   - Finished non-idle iterations in the window: ITERATIONS, with an assessment: ASSESSED
   - Iterations assessed in this cycle: N of sample size SIZE, of them problem iterations: N
   - Left for the next cycle (over sample size): LEFT
   - Active pairs agent × image version: PAIRS, pairs with at least one assessment: PAIRS_ASSESSED
   - Task assessments: N (KEY, ...)
   - Write failures: N
   - Candidates not assessed (budget): N
   - Cycle cost: X USD of budget_usd Y USD
   - Cost of one assessment: X USD (cycle cost / assessments written, iterations and tasks)
   CYCLE_EOF
   )
   ttasks comment CYCLE_TASK "$BODY"
   ```

6. Continue with the letters and the goal of the iteration. The cycle
   leaves no script or schedule behind.

### Assessor prompt

```text
You are the assessor of a review cycle. Read RUBRIC_PATH completely. For each
pair below, read the pack and write one JSON object to the out path, exactly
as the rubric says. Run no command and change no other file.
PACK_PATH -> OUT_PATH
...
```

`RUBRIC_PATH` is `SKILL_DIR/rubric.md`. Give the subagent the rubric path and
the pairs only: no expected scores and no opinion of your own.

## Limits

In review mode the only writes are `tariboy assessment add`, the one cycle
comment on `cycle_task` and the removal of an old `review-cycle` script. A
violation found by
an assessment stays in the assessment:

- never edit an image, workflow, skill or Store file because of it;
- never create a task, comment on an assessed task, or write to an assessed
  agent;
- never run `tariboy iteration tag` or another `tariboy` write.

| Thought | Reality |
| --- | --- |
| "This violation needs an improvement task now." | The assessment is the record. Improvement tasks come from the customer. |
| "A timeout or exit 137 iteration is not worth assessing." | Assess it; the rubric puts the defect in `summary` as `infra:`. |
| "I will assess this one again with better evidence." | An iteration with an assessment is processed. |
| "The budget is nearly spent, but the queue is short." | With `budget_usd`, stop at the budget; what is left is not assessed. |
| "There is no `budget_usd`, so I will set a limit myself." | Without `budget_usd`, assess the whole selection; `sample_size` is the limit. |
| "This pair already has 3 assessments; skip the rest of it." | There is no quota per pair. Take the selection of `candidates` as it is, up to `sample_size`. |
| "An idle iteration is cheap, so assess it too." | Idle iterations are not taken. |
| "A failed cycle stopped the schedule; I will create a script or a wake-up to recover." | The daemon starts the next cycle from the loop schedule. Create no script, schedule or `tariboy loop` change. |
| "The `review-cycle` script is still there; I will `rerun` it." | Remove it: `cancel` while active, then `rm`. |
| "This iteration came from a letter, but review mode is on, so I run a cycle." | Only a `schedule` or `manual` trigger runs a cycle. |
| "These old iterations were never assessed; take them now." | Only the last 24 hours count. Older ones are skipped. |
| "No iteration was left, so the cycle is done." | Run the task step: a `done` task with all iterations assessed still needs its task assessment. |
| "The comment can just say the cycle ran." | Fill every field of the comment template, `0` included. |
| "Writing `ttasks comment TASK "$BODY"` and saying every field is filled is enough." | Write the heredoc out with each filled line; a bare `"$BODY"` shows no comment. |
