# Ponytail session startup

Run each request in `cases.json` in a fresh Codex subagent with
`gpt-5.6-terra`, `medium`, and no inherited conversation. Supply the complete
ordered file prompts, runtime placeholders and manifest skill catalog with
readable paths. Permit only skill reads and simulated actions. Do not supply
`rubric.json`, other cases, proposed fixes or previous verdicts.

Baseline 0.13.7 omitted early Ponytail in all three cases (5/8 criteria).
Candidate 0.14.0 passed 8/8, both before and after the packaging compatibility
adjustment. Results retain abbreviated action traces and verbatim excerpts.
Provenance records input archives and SHA-256 of prompt and catalog sources.
These are single-sample decision simulations, not executed Native Task or
GitHub integrations. Minimal implementation and process compliance already
passed in baseline; no improvement in those dimensions is claimed.

The final minimal-case actor proposed observing a failing set-order test
without pinning PYTHONHASHSEED; failure is nondeterministic. Its proposed
customer response also used past tense despite simulation. These are
limitations outside the scoped routing criteria, not executed test evidence.
Startup actors inferred some existing slug behavior not supplied in fixtures.

Packaging is separate: direct upstream packaging failed on unsupported
`argument-hint`; the local copy removes only that field. The identity-bound
build then succeeded (digest in provenance). Repository checks and independent
skill evidence are recorded separately.
