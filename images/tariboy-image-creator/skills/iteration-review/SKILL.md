---
name: iteration-review
description: Use when a `script.result` letter of the `review-cycle` schedule arrives, when the user prompt has or lost a `## Review cycle` configuration, or when assessing other agents' finished iterations or done tasks with `tariboy assessment add`.
---

# Iteration Review

The review cycle assesses the finished iterations of the configured agents,
and their tasks after `done`, by rubric `iteration-review/1`, and writes each
assessment to the daemon. It runs once a day from one durable schedule, before
any goal work of that iteration. It changes nothing it assesses.

`REVIEW` below is `python3 SKILL_DIR/scripts/review.py`, with the absolute
path of this skill's directory. `WORKDIR` is the configured workdir.

## Configuration

The cycle runs only from this block of the user prompt. Without the block, or
with `review_mode: off`, review mode is off.

```markdown
## Review cycle

review_mode: on
agents: AGENT, AGENT, ...
since: RFC 3339 time — the date the cycle was enabled
budget_usd: 5
cycle_task: TASK-KEY
model: haiku
```

## Which step applies

| Observed | Step |
| --- | --- |
| Review mode on, any iteration | Ensure the schedule |
| `script.result` of `review-cycle`, review mode on | Run the cycle, then the rest of the iteration |
| `script.result` of `review-cycle`, review mode off | Stop the schedule |
| Review mode on, no such letter | No cycle in this iteration; continue the normal Flow |

## Ensure the schedule

1. Run `scripts/scripts.sh ls`. If a definition named `review-cycle` is
   `active`, or stopped by a letter delivered in this iteration, reuse it.
   Never create a second one.
2. With none, copy the script out of the image, so that the schedule outlives
   image updates, and create one schedule:

   ```bash
   mkdir -p "$WORKDIR/review-cycle"
   cp SKILL_DIR/scripts/review.py "$WORKDIR/review-cycle/review.py"
   scripts/scripts.sh schedule review-cycle --every 3600 -- \
     python3 "$WORKDIR/review-cycle/review.py" tick --state "$WORKDIR/review-cycle/tick.json" --period 86400
   ```

   `tick` exits `111` (quiet) until 24 hours have passed since its last
   result, so the schedule wakes the agent once a day. Record the `scr-...`
   ID in `context` as `CYCLE_TASK review-cycle`. Do not run a cycle until its
   first result.

## Stop the schedule

Run `scripts/scripts.sh cancel SCRIPT_ID` only while `ls` reports it
`active`, then `scripts/scripts.sh rm SCRIPT_ID`. Never `rerun` it. Reply to
the letter that review mode is off and the schedule is removed.

## Run the cycle

Do the cycle first in the iteration, before any goal work, so that its cost
holds only cycle work.

1. Set `START` to the current UTC time and `DIR="$WORKDIR/review/START"`.
2. `REVIEW candidates --dir "$DIR" --agents AGENTS --since SINCE --assessor tariboy-image-creator`
   selects the cycle's iterations and orders them:
   - only iterations that ended in the last 24 hours; an older iteration
     outside an earlier selection is skipped for good;
   - first every iteration with a problem: `harness_error`, not
     productive, a refused check, a question to the customer; newest first;
   - then, round by round over each pair agent × image version, the newest
     iterations until the pair has 3 assessments or no iteration is left.
   An iteration with an assessment from this assessor is processed: never
   assess it again, and never tag it.
3. Repeat while candidates remain:
   1. `REVIEW cost --agent tariboy-image-creator --since START` gives `spent`.
      `N = floor((budget_usd - spent) / 0.08)`, at most 10. When `N` is 0,
      stop: the rest of the selection is not assessed.
   2. `REVIEW pack --dir "$DIR" --limit N` writes one evidence pack for each
      of the next `N` candidates and prints `pack` and `out` paths.
   3. Start one subagent on the configured `model` with the assessor prompt
      below. Wait for it.
   4. `REVIEW validate --dir "$DIR"`. Delete each invalid output file; its
      iteration stays a candidate for the next cycle.
   5. `REVIEW add --dir "$DIR"` writes each valid assessment with
      `tariboy assessment add --file PATH`.
4. `REVIEW tasks --dir "$DIR" --assessor tariboy-image-creator` writes a task
   pack for each `done` task whose iterations are all assessed and that has
   no task assessment. Assess them with the same subagent, `validate` and
   `add` steps, inside the same budget.
5. `REVIEW cost --agent tariboy-image-creator --since START` gives the cycle
   cost, and `REVIEW coverage --agents AGENTS --since SINCE --assessor tariboy-image-creator`
   gives metric 1. Post one comment on `cycle_task` with: the window, active
   pairs agent × image version, pairs with coverage (3 assessments, or all
   iterations of the pair), iterations assessed, task assessments, write
   failures, candidates not assessed, the cycle cost, and the cost of one
   assessment = cycle cost / assessments written.
6. `scripts/scripts.sh rerun SCRIPT_ID` of `review-cycle`. Then continue with
   the other letters and the goal of the iteration.

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
comment on `cycle_task` and the `review-cycle` schedule. A violation found by
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
| "The budget is nearly spent, but the queue is short." | Stop at the budget; what is left is not assessed. |
| "These old iterations were never assessed; take them now." | Only the last 24 hours count. Older ones are skipped. |
