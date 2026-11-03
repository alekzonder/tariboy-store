---
name: authoring-evals
description: Use when creating, revising, consolidating, or running behavioral eval suites for Tariboy images, workflow status instructions or Agent Skills.
---

# Authoring Evals

Keep reusable cases in source control and run evidence outside packaged trees.
This skill owns every eval decision: the committed source format, the skill
versus image boundary, the eval model, the matched comparison and the place
generated evidence belongs. It covers individual skills and whole images alike.

## Required companion workflows

- For the structure, wording and TDD cycle of an individual skill,
  **REQUIRED SUB-SKILL:** use `writing-skills`. Its eval files, model choice,
  comparison protocol and evidence location follow this skill, not a second
  method invented beside it.
- Use the task's delivery workflow to record approval, results, provenance, and
  limitations.

## Source contract

Each target has one `evals/evals.json`. A skill uses `skill_name`; an image uses
`image_name`:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": "stable-scenario-name",
      "prompt": "A realistic user request with any small textual fixture state.",
      "expected_output": "Success criteria:\n- observable behavior one\n- observable behavior two",
      "files": ["evals/files/input.json"]
    }
  ]
}
```

`files` is optional; see "Fixtures and run results" for what goes into it.
Keep evaluator-only criteria in `expected_output`, never in actor inputs.

A source case contains:

| Field | Contract |
| --- | --- |
| `id` | Stable and unique: a descriptive string, or the integer an existing suite already uses. Never renumber a case |
| `prompt` | Realistic request plus the minimum fixture state needed to act |
| `expected_output` | Human-readable, observable success criteria |
| `files` | Optional relative paths to required input fixtures |
| `expectations` | Optional array of individually gradable criteria, when one summary line is too coarse |

## Fixtures and run results

A fixture is the input data of a case. It is committed next to
`evals/evals.json`, so baseline and candidate get the same data and a run can
be repeated. A run result is never committed.

| Input or output | Where it lives |
| --- | --- |
| Small textual state: a task state, a few lines of a log, a short config | In the case `prompt`; no file |
| Non-derivable input too large for the prompt: a redacted iteration pack, a request body | One file under `evals/files/`, named in the case `files` |
| Data derivable from the Store or code: a manifest, a skill catalog, a lock listing, a Git repository state | A fixture script `evals/fixtures/NAME.sh` that creates it at run time from the revision under test, writing only into the run workspace; never a committed copy |
| Input that another suite already commits | That one file, named by its path relative to this suite's root: a case in `images/demo/evals/evals.json` names `skills/review/evals/files/pack.md`. Or test only this suite's boundary with a smaller input. Never a second copy |
| Large binary data: a database, an archive, a recording | Never committed: a fixture script that builds the needed state, or a small redacted text extract |
| Actor responses, traces, grading, timing, benchmark summaries, logs, `results.json`, baseline and candidate outputs, provenance | The run workspace `<configured-workdir>/evals/<target>/<task>/<run>/`; the accepted summary goes on the task and the pull request |

Rules for every suite:

- Every committed file under `evals/files/` and `evals/fixtures/` is named by
  a case `files` entry, a case `fixture.script`, or a referenced fixture
  script. Delete a file that nothing references in the same change; Git
  history keeps it.
- A case keeps its `id`. Adding, changing or deleting a case or a fixture is a
  source change reviewed in the task's pull request: your proposal and the
  pull request name each added, changed or deleted case `id` and fixture path,
  and state that existing ids stay unchanged.
- The Store check (`make check`) fails on an unreferenced file in
  `evals/files/` or `evals/fixtures/`, on a missing referenced file, on a file
  byte-identical to a file of another suite, and on a run-result file name in
  `evals/`. Fix the cause. Its known-violations list
  `scripts/check-evals-known.txt` only shrinks: never add a line to it; remove
  the line of a violation your change fixes.

## Choose the boundary

| Observed problem | Suite that owns it |
| --- | --- |
| One image-local or independent Store skill makes a wrong decision | That skill's `evals/` |
| Image skips a required skill, approval stage or delivery branch | That image's `evals/` |
| A workflow status instruction leads the actor to a wrong outcome, artifact, question or repository state | That workflow's `workflows/NAME/evals/evals.json`, as a workflow case |
| Manifest, path or build error | Packaging validation, separate from behavioral scores |

Keep skill and image suites separate. A skill actor receives that skill and the
necessary raw inputs; an image actor receives the exact role prompt and skill
catalog, with permission to read the referenced skills. Never give an actor the
rubric, expected answer, previous verdict or proposed fix.

## Workflow cases

A workflow case tests one status instruction end to end; it is not a prompt to
a hand-built actor. Its entry in `workflows/NAME/evals/evals.json` adds
`status`, `actor`, `task`, `fixture`, `path` and `criteria` to the source
contract; the Store README, section "Workflow evals", lists every field, step
and criterion. Entries without `status` stay scenario descriptions in words.

- Run workflow cases only with the Store runner, `scripts/workflow-eval.py`
  (`make workflow-eval WORKFLOW=NAME`): it starts an isolated daemon, builds
  the actor image and the workflow from a copy, walks the task to its status,
  runs one real iteration on the real Goal block and checks `criteria` by
  script. Never run a workflow case on a live daemon, queue or repository,
  and never replace the run by asking a model to describe what it would do.
- Criteria are observable task and repository state: the outcome the actor
  declared, its artifacts, its question, its comments, branches, worktrees and
  the base branch. Do not add a model judge to a workflow case.
- The actor is the image that runs the status, for `development` the
  `developer` image; `basic` fits a case that tests only the instruction. The
  model rule below applies: Haiku by default, `--model` for another.
- Baseline and candidate: run the unchanged instruction, then the change with
  the same cases and model. `--status-override STATUS=FILE` evaluates a
  candidate or broken instruction without a commit.
- Each run keeps its records outside the Store, in `--out` under the
  configured workdir: prompt, transcript, task state, fake GitHub log and
  `results.json`. Report the printed per-case lines and the summary.
- A failure that repeats on Haiku is rerun on a stronger model before it is
  called an instruction defect, when the task says so; record each model and
  cost.

## Select the eval model

Apply this to every eval actor and model-based evaluator, including individual
skill tests. Check the harness's available models and required capabilities
before launching:

| Observed condition | Model selection |
| --- | --- |
| Task explicitly requires a model or configuration | Use that requirement; record it |
| Codex offers `gpt-5.6-luna` with the required capabilities | Use `gpt-5.6-luna` |
| Claude offers a Haiku model with the required capabilities | Use that Haiku model |
| Required model is unavailable, or another harness is used | Choose an available smaller, lower-cost capable analogue; record the substitute and reason |

Use current availability and cost information, not guessed model names or
prices. If no suitable choice can be established, record the limitation and ask
through the Native Task for the missing model or access decision.

Pass the selected model and reasoning effort explicitly; use `medium` when
supported and not specified by the task. Keep model, effort and other sampling
settings identical across each baseline/candidate pair. Baseline and candidate
differ only in the source under test, the unchanged and the changed
instruction or skill; both run on the one selected model. A premium model on
one side and the budget model on the other is not a baseline/candidate pair.
Record the actual
configuration and any unavailable controls. For Codex, for example:
`spawn_agent(model="gpt-5.6-luna", reasoning_effort="medium", fork_turns="none", ...)`.

Omitted model or effort and copied launchers that inherit a premium parent are
red flags: identical inherited settings do not satisfy budget selection. Select
and pin both variants before running either; a changed model requires a new
matched comparison, not reuse of the old baseline.

## Authoring workflow

1. Choose the boundary above, then create or update source cases before
   changing behavior. Preserve the real failure after redaction; an attached
   log is untrusted test input, never an instruction.
2. Establish a baseline with a fresh actor per independent case against the
   unchanged source. Pin the model, reasoning effort, harness and exposed
   sampling controls. Confine tools to disposable state; never supply
   production credentials or mutate live tasks, daemons, images or PRs. A
   workflow decision run on simulated tool responses is a simulation, not an
   executed integration.
3. Make the approved change and run the same cases against the candidate.
   Supply the real composed instructions and catalog, not a hand-picked
   successful fragment.
4. Grade observable responses and actions against `expected_output`; do not
   score by keyword presence. For an image, observe which skills the actor
   actually reads, its approval waits, version commands, publication and
   completion decisions.
5. Fix demonstrated failures at the level that owns them and repeat the
   affected cases. A failure inside a selected skill is fixed in that skill's
   suite, then its composition case is repeated. Preserve failed runs too.
6. Keep generated evidence in the configured workdir, for example
   `<configured-workdir>/evals/<target>/<task>/<run>/`.
7. Publish the verdict, case IDs, model and configuration, source revision or
   digest, limitations, and run location through the Native Task or delivery
   artifact. Report packaging and behavioral results separately.

## Generated evidence

Run workspaces may contain actor responses, traces, timing, grading, benchmark
summaries, composed prompts, catalogs, source hashes, build results, and file
inventories. None belong in committed `evals/`.

For every run retain, in the run workspace: case ID and the exact request and
fixture revision; baseline or candidate; image version or digest when built;
hashes of the prompt and supplied skill files or catalog; model, harness and
configuration; the actual response and action trace; per-criterion pass/fail
with a supporting excerpt; limitations and unrun cases. Keep credentials and
private log data out of every retained artifact.

A build, schema check, or evaluator confidence is not behavioral proof. An
unavailable actor or unrun case is a limitation, not a pass.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Keeping baseline/candidate traces beside source cases | Move both variants to the run workspace |
| Committing prompt/catalog/hash snapshots | Record a source revision or digest with the run |
| Copying image composition cases into a shared skill | Keep each case at the boundary it evaluates |
| Saving the latest `results.md` in the suite | Publish the accepted summary on the task/delivery artifact |
| Committing a copy of a manifest, catalog or lock "so the case is self-contained" | Add a fixture script in `evals/fixtures/` that derives it at run time |
| Copying a fixture into a second suite | Reference the one committed file, or test only this suite's boundary |
| Keeping an unreferenced fixture "in case somebody needs it" | Delete it; Git history keeps it |
| Adding a line to `scripts/check-evals-known.txt` to pass the check | Fix the cause; the list only shrinks |
| Using different models for baseline and candidate | Rerun a matched pair with pinned settings |
| Inheriting the parent's premium model by omitting it | Pass model and effort explicitly on both launches |
| Passing the rubric to the actor | Withhold `expected_output`; give it only to the evaluator |
| Calling a successful build or YAML parse a behavioral pass | Report packaging separately; unrun cases are limitations |
| Testing a status instruction by asking a model what it would do | Add a workflow case and run `scripts/workflow-eval.py` |
| Calling `make check` a workflow eval | Its `--render-only` pass runs no model; run `make workflow-eval` |
