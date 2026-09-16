# Image creator behavioral evals

Use `tariboy-image-evals` for this image suite and existing `writing-skills`
for each independent suite under `../skills/*/evals/`. This directory contains
scenario data and evidence, not another skill-writing procedure or eval engine.

## Run

Before launching actors or model-based evaluators for either suite, apply
`tariboy-image-evals` → **Select the eval model**. Pin Codex to available
`gpt-5.6-terra` with explicit effort (normally `medium`); otherwise select a
currently available budget analogue and record why. Preserve explicit task
model requirements. Use the same model, effort and sampling settings for each
baseline/candidate pair; do not inherit the parent preset. Record unavailable
controls. The inherited settings below describe historical runs only.

1. Choose a suite and read its `rubric.json` as evaluator. Send an independent
   fresh-context actor only the request(s) from `cases.json`, required raw
   fixtures and the instructions under test. With a harness supporting tools,
   confine it to disposable state and fake task/PR responses. Never use live
   credentials, tasks, daemons or repositories for simulated actions.
2. For the legacy control supply only `skills/image-creator/SKILL.md`.
   For an individual candidate supply only its `SKILL.md`; let it name required
   dependent skill invocations without claiming it executed unavailable bodies.
   For composition supply `instructions.md`, the manifest skill catalog with
   resolved paths, and access to selected skill bodies. Do not supply rubric,
   spec, plan or earlier answers. Baseline and candidate use identical requests.
3. Ask the actor to apply the instructions and report concrete next actions,
   commands, skill reads and uncertainty. Tool restrictions take precedence over
   all simulated lifecycle instructions: no writes, services or `i-am-done`.
4. Save the verbatim response and actual tool trace if available. Score each
   criterion by reading actions and their order, not by matching phrases.
   Record source hashes, harness/model, fixtures, failures and limitations.
5. Repeat failed cases after supported corrections. Run fresh per-case trials
   and pressure/wording repetitions prescribed by writing-skills before claiming
   robustness; the initial simulations below are single-sample smoke evidence.

## Initial evidence: 2026-09-09

Harness: Codex collaboration subagents, `fork_turns: none`, inherited model and
effort. Exact model identifier, sampling configuration and seed are not exposed
by this tool; no model-specific reliability claim is made. Actors could only
read allowed files and propose actions; later separate archival calls wrote
responses. No live daemon, Native Task or GitHub action was part of an eval.

`baseline.md` records one legacy-control actor for A–H. The three candidate
actors each received only their domain skill and corresponding requests.
`baseline-role.md` and `candidate-role.md` record the legacy-control and
candidate composition actors for I–L. Cases within a suite shared one actor
context; these are independent suite-level samples, not per-case repeated
trials. Full responses are preserved; parent/evaluator verdicts and hashes are
in `results.json` and each skill’s `evals/results.json`.

The skill type under test is reference/procedure guidance and rule adherence;
no comparative wording optimization was performed in the initial run. The
follow-up summarized below adds five repetitions per delivery variant.
Statistical robustness is not claimed. The initial control
already resisted log injection and premature behavioral-success claims; these
passing controls remain regression coverage rather than new improvements.

The composition run used the source prompt and manifest catalog, selected
skill bodies and simulated task facts. It did not launch a Tariboy agent or
exercise a real harness bridge, and omitted unspecified runtime workdir data;
the candidate explicitly requested that missing fact. This proves the observed
routing decisions under those inputs, not end-to-end task execution. Packaging
is verified separately by the real Go image builder below.

## Review follow-up

The initial single-sample evidence did not satisfy the writing-skills repeated
trial requirement for delivery rules. Five fresh legacy-control and five fresh
candidate runs were therefore evaluated, plus fresh per-case composition
controls/candidates I–L. The candidate delivery result was 5/5 complete against
0/5 complete controls. Composition I, J and L passed; K retained a strict
failure because it omitted future base synchronization while correctly waiting
for approval. Supplemental K2, with approval already recorded, passed the
required preflight → fetch/fast-forward-only → worktree order. Aggregated
criteria, source hashes and limitations are in `results.json`; one-off actor
transcripts are not maintained as image source.

The fresh K response correctly waits for plan approval but omits explicit base
synchronization from its abbreviated future plan; its strict rubric failure
is retained. K2 separately supplies recorded approval and checks the executable
branch-setup stage, including preflight and base synchronization before worktree
creation. This distinguishes an incomplete future-step description from an
observed out-of-order mutation; no live mutations were performed in either run.

## Model-selection regression: 2026-09-10

Use `model-cases.json` and `model-rubric.json` in this directory for composition
I1–I2, and the corresponding files in
`../skills/tariboy-image-evals/evals/` for individual skill cases M1–M4.
Supply one case per fresh actor; repeat M1 five times per variant. Baseline is
the complete pre-change source at `9ebbaea`; candidate is image `0.1.6`.
For composition, resolve every manifest skill path before launching; verify
baseline/candidate catalog names match and every referenced body is readable.

All real actors used Codex `gpt-5.6-terra`, explicit `medium`, and
`fork_turns: none`. The models in case fixtures are simulated choices, not
extra paid launches. Both `model-results.json` files preserve source/fixture
hashes, configuration, actor responses, criterion verdicts and limitations.

The skill suite passed 5/8 baseline and 8/8 candidate runs; the repeated M1
budget choice improved from 3/5 to 5/5. Missing-Terra, other-harness and explicit
task-override cases passed in the candidate. Composition improved from 0/2 to
2/2: standalone skills read the shared selection rule, and whole-image evals
pin the budget model. Two initial candidate composition attempts had an empty
catalog due to a local fixture-generation error; they are retained as invalid
inputs, excluded from totals, and replaced by fresh runs with all 28 skills.
These are decision simulations, not billing measurements or live integrations;
only M1 has repeated samples. Packaging remains a separate check.

## Mechanical checks (from repository root)

```bash
make check
```

The gate restores locked upstream skills in a temporary Store copy and builds
every declared image against a temporary isolated daemon. The checkout and live
daemon remain untouched. Do not label these checks behavioral evals or a
production image publication.

## Instruction file standard: 2026-09-16

Composition cases I, K, P4 and W1 were rerun for the standardized
`instructions.md` (six fixed sections with a Flow contract table). Harness was
Claude Code fresh-context subagents, one per case, on `claude-sonnet-5`, which
is this harness's budget analogue for the unavailable `gpt-5.6-terra`; the
substitute and the absent reasoning-effort control are recorded in
`improve-109-results.json`. The first candidate exposed two real regressions —
an actor that read no skill body because the Flow table looked complete, and a
recovered wait that made no task write — and those runs are preserved in
`improve-109-candidate-v1.md`. Both were fixed in the instructions and the
standard, and the reruns pass. Authoring-side evidence for the standard itself
lives in `../skills/tariboy-image-authoring/evals/improve-109-*`.

`make check` fails identically on unmodified `origin/main` in this environment
(`unknown plugin "llm-as-judge"` from the daemon image build); every earlier
stage of the gate passes. The changed image was packaged separately through the
authorized build launcher, digest
`ea60d3b4c5d41b90189955798202112d9930ddfc6c1ce761ab45166724db6ae5`.
