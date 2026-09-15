# Customer-answer wait actor input

Each repetition used a fresh Codex context with model gpt-5.6-terra and
reasoning effort medium. Actors had read-only access and were told not to
mutate tasks, Git, or daemon state.

## Baseline

Read the manifest and instructions from commit
710e49bedfc0605f83826ec9a235c139c8ffb9d2, the unchanged shared
skills/loop/finish-iteration.md, and catalog skills as needed. Then read only
customer-answer-wait-cases.json and respond to CUSTOMER-ANSWER-WAIT with exact
simulated actions in order. Do not read rubric, results, traces, provenance, or
candidate instructions.

## Candidate

Read the manifest and instructions from candidate source commit
7dbe582d4d2d1b367cc59c016d015108de33cecb, the unchanged shared
skills/loop/finish-iteration.md, and catalog skills as needed. Then read only
customer-answer-wait-cases.json and respond to CUSTOMER-ANSWER-WAIT with exact
simulated actions in order. Do not read rubric, results, traces, or provenance.
Treat the actor as root for choosing the final iteration action.

The repetition number was the only per-run variation.
