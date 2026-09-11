# Developer image behavioral evals

Use `writing-skills` and the image composition workflow in
`tariboy-image-evals`. Give a fresh-context actor the case request, the real
image instructions and skill catalog, but not the rubric or prior responses.
Simulate actions only; do not use live tasks, repositories or credentials.

## Post-merge CI reuse

`post-merge-cases.json` and `post-merge-rubric.json` define a separate four-case
composition regression. `post-merge-results.json` contains per-criterion
verdicts in rubric order, action-trace excerpts (repeated script paths and
publication bodies abbreviated), and verbatim supporting response excerpts.
`post-merge-provenance.json` records source hashes, build digests and harness.

Run each case in a fresh Codex subagent with `gpt-5.6-terra`, effort `medium`,
`fork_turns: none`. Supply the complete image instructions, the manifest's
skill catalog (name, description, readable resolved path), and
`skills/loop/finish-iteration.md`, followed by that case's request. Permit only
reading the referenced skills; request simulated commands and publication.
Never supply the rubric, other cases, previous verdicts or the proposed fix.
Repeat with the same model/configuration for baseline and candidate.

Baseline is commit `c842239`, image 0.13.4; candidate is 0.13.5. The baseline
reran `make check` on refreshed main despite successful final-head CI. Candidate
passed all ten scoped workflow criteria across four cases: update main and
verify merge ancestry, reuse final-revision CI, block completion on divergent
main or stale CI, and preserve local-merge verification.

These are single-sample decision simulations, not executed GitHub integration
or shell-validity tests. Actors used abbreviated/fake SHAs and some malformed
launcher paths; baseline also proposed `git ... make check`. Both local-merge
actors assumed the proposed check succeeded, although its result was not in
the fixture. The stale-CI actors named the missing CI event without demonstrating
a durable subscription. Those limitations do not establish executable
end-to-end workflow success. No individual skill changed or received a new
independent evaluation.

Packaging was checked separately: baseline and candidate builds succeeded via
the identity-bound image-creator launcher. The repository baseline `make check`
passed 21 Store tests and `test-check-images.sh`, then failed while building the
unchanged reserved `basic:latest` image with daemon 0.56.0. This is not reported
as a passing repository-wide check.
