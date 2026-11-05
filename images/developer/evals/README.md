# Development task workflow behavioral evals

`evals.json` is the only case source in this directory: whole-image composition
and routing cases for `developer`. Individual skill behavior belongs to
`../skills/*/evals/evals.json`.

The cases cover the three iteration modes:

- `workflow`: the `WORKFLOW-*` cases and `MODE-LINE-WORKFLOW-FALLBACK`.
- `flexible`: the cases without a prefix and `MODE-LINE-FLEXIBLE-VS-LETTER`.
- `request`: the `REQUEST-*` cases.

The `MODE-LINE-*` cases put the daemon line `` Iteration mode: `NAME`. `` in
the prompt and make the Goal block, or a letter, say a different mode. The
other cases have no mode line, so the agent must use the Goal block.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
It owns the source contract, the skill-versus-image boundary, the eval model
selection and the matched baseline/candidate protocol. Generated run evidence —
actor responses, traces, grading, hashes, composed prompts, build results —
belongs in the configured workdir, not here. Accepted verdicts, provenance and
limitations are published on the Native Task.

The cases carry their fixture state in `prompt` and name no `files`, so this
suite commits no fixture.

Packaging is validated separately from behavior:

```bash
make check
```

The gate restores locked upstream skills in a temporary Store copy and builds
every declared image against a temporary isolated daemon. A successful build is
never behavioral proof.
