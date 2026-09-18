# Image creator behavioral evals

`evals.json` is the only source in this directory: whole-image composition and
routing cases for `tariboy-image-creator`. Individual skill behavior belongs to
`../skills/*/evals/evals.json`.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
It owns the source contract, the skill-versus-image boundary, the eval model
selection and the matched baseline/candidate protocol. Generated run evidence —
actor responses, traces, grading, hashes, composed prompts, build results —
belongs in the configured workdir, not here. Accepted verdicts, provenance and
limitations are published on the Native Task.

Packaging is validated separately from behavior:

```bash
make check
```

The gate restores locked upstream skills in a temporary Store copy and builds
every declared image against a temporary isolated daemon. A successful build is
never behavioral proof.
