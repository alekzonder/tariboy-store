# Release skill evaluations

These are simulated operator decisions, not executed Git releases, Native
Tasks, CI runs or artifact uploads. Actors run in fresh contexts on Codex
`gpt-5.6-terra`, reasoning effort `medium`; no other sampling controls are
exposed. No model-based judge is used. Cases and evaluator-only criteria are
in `cases.json`; actors receive only the request and release guidance.

For a rerun, start a fresh actor for each case and each variant. Have it read
the complete baseline `full/baseline-guidance.md` or candidate `../SKILL.md`,
and required shared skill bodies when requested. Ask for concrete proposed
actions and stopping point, with no live actions. Save exact actor request,
response and hashes of read files; score observable actions against each
criterion manually. Do not supply the rubric or prior verdict to the actor.

`full/` retains exact prompts/responses from the complete-guidance runs,
including the initial candidate CLI failure and its corrected repeat. The
first candidate invented `ttasks whoami` and treated all `ttasks create`
stdout as a task key. The final skill specifies the real launchers and reading
the structured returned key. Source snapshots retain the earlier guidance.

The earlier condensed-guidance and mispaired runs are exploratory only.
Their files preserve the failure and provenance limitations; they are not
matched evidence for the final skill. No-guidance approval repetitions also
measure only text responses, not actual tool writes. See final results for
which exact candidate revision and observations support the conclusion.
