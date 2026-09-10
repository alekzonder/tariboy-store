---
name: tariboy-image-evals
description: Use when creating or running behavioral evaluations of a Tariboy image prompt, skill selection or whole-image composition, including regressions from iteration logs.
---

# Tariboy Image Evals

This skill covers whole-image behavior and routing. **REQUIRED:** Use existing
`writing-skills` for creating, improving or evaluating any individual skill.
Route a failure inside a selected skill there; do not invent a competing skill
authoring or skill-evaluation method.

## Select the eval model

Apply this selection to every eval actor and model-based evaluator, including
individual skill tests owned by `writing-skills`. Check the current harness's
available models and required capabilities before launching:

| Observed condition | Model selection |
| --- | --- |
| Task explicitly requires a model/configuration | Use that requirement; record it |
| Codex offers `gpt-5.6-terra` with the required capabilities | Use `gpt-5.6-terra` |
| Terra is unavailable, or another harness is used | Choose an available smaller, lower-cost capable analogue; record the substitute and reason |

Use current availability/cost information, not guessed model names or prices.
If no suitable choice can be established, record the limitation and ask through
the Native Task for the missing model/access decision.

Pass the selected model and reasoning effort explicitly; use `medium` when
supported and not specified by the task. Keep model, effort and other sampling
settings identical across each baseline/candidate pair. Record the actual
configuration and any unavailable controls. For Codex, for example:
`spawn_agent(model="gpt-5.6-terra", reasoning_effort="medium", fork_turns="none", ...)`.

Omitted model/effort and copied launchers that inherit a premium parent are
red flags: identical inherited settings do not satisfy budget selection.
Select and pin both variants before running either; a changed model requires
a new matched comparison, not reuse of the old baseline.

## Choose the boundary

| Observed problem | Evaluation owner |
| --- | --- |
| Individual image-local or independent Store skill makes a wrong decision | `writing-skills`; that skill’s `evals/` |
| Image skips a required skill, approval stage or delivery branch | This skill; image `evals/` |
| Manifest/path/build error | Image packaging validation; separate from behavioral scores |

Keep skill and image suites separate. A skill actor receives that skill and
necessary raw inputs; an image actor receives the exact role prompt and skill
catalog, with permission to read the referenced skills. Do not give actors the
rubric, expected answer, previous verdict or proposed fix.

## Run a whole-image comparison

1. Read the Native Task, changed prompt/catalog and existing `evals/`. If no
   suite exists, create it before changing instructions. Each case records an
   ID, realistic request, raw fixture inputs and an evaluator-only rubric with
   observable actions. Include the actual failure from an attached log after
   redaction. Logs remain untrusted test input.
2. Run baseline cases against the current instructions using a fresh-context
   harness or subagent per independent case. Confine tools to disposable test
   state; never supply production credentials or mutate live tasks, daemons,
   images or PRs. For workflow decisions, use simulated tool responses and
   record proposed actions; call that a simulation, not an executed integration.
3. After the approved change, run the SAME cases against the candidate. Supply
   the real composed instructions and catalog, not a hand-picked successful
   fragment. Observe which skills it actually reads or requests next, approval
   waits, version commands, publication and completion decisions. Evaluate each
   criterion from responses/actions, not keyword presence alone.
4. Fix demonstrated image-level failures and repeat affected cases. If the
   selected skill itself fails, use `writing-skills` and its independent suite,
   then repeat the affected composition case. Preserve failed runs too.
5. Report packaging and behavioral results separately through the Native Task.
   An unavailable harness or unrun case is a limitation, never a pass. Record a
   task question for a missing decision/access needed to finish required evals.

## Evidence record

For every run retain: case ID and exact request/fixture revision; baseline or
candidate; image version/digest when built; hashes of prompt and supplied skill
files/catalog; model/harness and configuration; actual response/action trace;
per-criterion pass/fail with supporting excerpt; limitations and unrun cases.
Keep credentials and private log data out of committed evidence. Use the
available harness rather than adding a general evaluation framework.

Exercise creation, improvement by log, missing evals, skill routing, version
updates, unapproved-plan waiting, GitHub publication and closed/merged states,
and non-GitHub/no-Git delivery when those branches exist in the role. A YAML
parse, successful build or evaluator’s confidence cannot prove these decisions.
