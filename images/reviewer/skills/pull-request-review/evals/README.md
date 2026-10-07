# pull-request-review behavioral evals

`evals.json` is the only case source in this directory: the skill's own
decisions when reviewing and publishing a pull request review. Whole-image
routing belongs to `../../../evals/evals.json`; the utility is tested by
`../tests/test_github_review.py`.

**REQUIRED:** Use `authoring-evals` before changing a case or launching a run.
Generated run evidence belongs in the configured workdir, not here. Accepted
verdicts, provenance and limitations are published on the Native Task.
