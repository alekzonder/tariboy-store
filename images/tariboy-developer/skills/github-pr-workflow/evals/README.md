# GitHub PR workflow behavioral evals

`evals.json` is the only case source in this directory: cases for the
image-local `github-pr-workflow` skill alone. Whole-image composition and
routing belong to `../../../evals/evals.json`.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
It owns the source contract, the skill-versus-image boundary, the eval model
selection and the matched baseline/candidate protocol.

Give a fresh-context actor only `../SKILL.md` and the case `prompt`. Never give
it `expected_output`, an earlier verdict or a proposed fix. Simulate proposed
actions only; use no GitHub credentials and no live repositories.

Generated run evidence belongs in the configured workdir, not here. Accepted
verdicts, provenance and limitations are published on the Native Task.
