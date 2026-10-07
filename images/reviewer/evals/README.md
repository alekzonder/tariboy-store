# Reviewer behavioral evals

`evals.json` is the only case source in this directory: whole-image
composition and routing cases for `reviewer` working tasks of the `pr-review`
workflow. The `pull-request-review` skill's own behavior belongs to
`../skills/pull-request-review/evals/evals.json`; the workflow's scripts are
tested by `../../../workflows/pr-review/tests/`.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
It owns the source contract, the skill-versus-image boundary, the eval model
selection and the matched baseline/candidate protocol. Generated run evidence
belongs in the configured workdir, not here. Accepted verdicts, provenance and
limitations are published on the Native Task.

Packaging is validated separately from behavior with `make check`. A
successful build is never behavioral proof.
