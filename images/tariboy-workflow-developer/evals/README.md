# Workflow development agent behavioral evals

`evals.json` is the only case source in this directory: whole-image
composition and routing cases for `tariboy-workflow-developer` working tasks
of the `development` workflow. Individual skill behavior belongs to
`../skills/*/evals/evals.json`; the workflow's checks are tested by
`../../../workflows/development/tests/`.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
It owns the source contract, the skill-versus-image boundary, the eval model
selection and the matched baseline/candidate protocol. Generated run evidence
— actor responses, traces, grading, hashes, composed prompts, build results —
belongs in the configured workdir, not here. Accepted verdicts, provenance and
limitations are published on the Native Task.

Packaging is validated separately from behavior:

```bash
make check
```

A successful build is never behavioral proof.
