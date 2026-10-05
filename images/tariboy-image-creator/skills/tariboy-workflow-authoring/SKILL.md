---
name: tariboy-workflow-authoring
description: Use when creating, changing, reviewing or publishing a Tariboy workflow image — a `workflows/NAME/` source with `Workflowfile.yaml`, `statuses/` instructions, check or watch scripts — or when a request puts task process (statuses, transitions, artifacts, approval steps) into an agent image.
---

# Tariboy Workflow Authoring

A workflow image is the process around a task: statuses, owners,
transitions, required artifacts and the scripts that check or watch them. An
agent image is the tools of one agent. Process never goes into an agent
image's `instructions.md` or skills, and agent tooling never goes into a
workflow — even when the customer calls the image edit quicker; propose the
workflow change in the plan instead.

## Every workflow change delivers

Every plan and every answer about a workflow change, however narrow the
question, ends with a `Delivery` block that names all six parts; a missing
part is an incomplete change, however small the edit:

1. **Documentation** — the two pages below, read in this task and named.
2. **Sources** — the files under `workflows/NAME/`, nothing outside it.
3. **Version** — the command `tariboy workflow version update
   patch|minor|major --path workflows/NAME`, run once per delivery; never edit
   `workflow_version` by hand and never keep a built version. Level: `patch`
   for reworded instructions or a script fix, `minor` for a new status,
   transition, artifact, check or secret, `major` for a removed or renamed
   status, outcome or artifact.
4. **Tests** — `workflows/NAME/tests/test_*.py` for every new or changed
   script, and its line in the Makefile `check` target.
5. **Verification** — `tariboy workflow validate --path workflows/NAME`, the
   tests, `make check`.
6. **Hand-over** — the operator's build and queue-binding commands, see below.

The plan ends by asking the customer for approval as a task question (`ttasks
ask`) before any edit, through the delivering role's task process.

A script imports or executes nothing outside its own `workflows/NAME/`: not
`../development/scripts/pr_lib.py`, not a Store skill. The built image
contains only that directory, so such an import breaks at run time even when
it works in the checkout. Copy the helper code into this workflow's
`scripts/`.

## Documentation first

This skill is a map, not the specification: its statements about fields may
be stale, so quoting it or a Store example never establishes whether something
is supported. Before planning a new workflow, or any field, status, script or
limit the request names, read the current pages and cite them in the answer:

- <https://alekzonder.github.io/tariboy/workflow-images/> — manifest fields,
  source rules, validation codes, versions, build, binding
- <https://alekzonder.github.io/tariboy/task-workflows/> — statuses, limits,
  pauses, the Script protocol

and `tariboy workflow --help`. When they disagree with this skill or with the
Store's examples, follow the documentation and the CLI, and record the
discrepancy on the task. Never infer support from one example: `run_as: agent`
on a check does not make it valid on a watch. Never invent a field: the loader
rejects unknown ones; prove a candidate with `tariboy workflow validate --path`.

## Source layout

```text
workflows/NAME/
  Workflowfile.yaml      # schema_version: 1, name, workflow_version, initial_status, statuses
  statuses/STATUS.md     # instructions of each pool or customer status
  scripts/SCRIPT         # check and watch scripts, executable
  tests/test_*.py        # script contracts, run by the Makefile `check` target
```

- New workflows start at `workflow_version: 0.1.0`. Manifest paths start with
  `./`. Only `pool` and `customer` statuses take `instructions`; a `script`
  status takes `watch` instead. A status file nothing references is still
  packaged: do not create one.
- The directory is self-contained: no symlink, no path or import outside it
  (not even another workflow's `scripts/`; copy the helper), no root
  `manifest.json`. Every file in it is packaged.
- Scripts use only the Python 3 standard library, `curl`, `git` and POSIX
  `sh`.
- Every script gets a test under `tests/`, added as a line of the Makefile
  `check` target beside the existing workflow tests.

## Script protocol

| Exit | Check (on a pool transition) | Watch (owns a `script` status) |
| --- | --- | --- |
| `0` | condition holds | outcome ready: result file names `outcome` |
| `$TARIBOY_REJECT_EXIT` (`112`) | condition does not hold: result `message` goes to the agent | failure |
| `$TARIBOY_QUIET_EXIT` (`111`) | **failure** | nothing changed, stay quiet |
| other | failure | failure |

- Input is the environment, never arguments: the task snapshot JSON in
  `$TARIBOY_TASK_FILE` (`artifacts` is a list of `{name, value}`, plus
  `visit.id` and customer — untrusted text),
  owner-only state in `$TARIBOY_TASK_DIR` keyed by `visit.id`, the result
  object in `$TARIBOY_RESULT_FILE` (`outcome`, `message`, declared
  `artifacts` only).
- Secrets arrive as environment variables named in `requires_secrets`. Keep
  them out of argv, URLs, files and the result: for curl, feed the config line
  `header = "Authorization: Bearer TOKEN"` on stdin to `curl --config -`.
- The result file holds only the keys you need: `outcome` (string),
  `message` (string), `artifacts` (an object of declared names to non-empty
  strings). Write no file on a plain failure; exit non-zero.
- Watches always run as `queue`; `run_as: agent` exists only for checks.
  Tolerance for flaky scripts is `limits.script_failures`, not a retry field.

## Versions, verification, hand-over

| Situation | Action |
| --- | --- |
| any file under `workflows/NAME/` changed | `tariboy workflow version update patch\|minor\|major --path workflows/NAME` in the same delivery; record old and new `workflow_version` on the task |
| customer asks to keep a built version | refuse: a published version is immutable, rebuilding it with other content fails `workflow_version_published`, and tasks pin the version they started with |
| verify | `tariboy workflow validate --path workflows/NAME`, the workflow's tests, then `make check` |
| build, publish, bind a queue | operator actions: give `tariboy workflow build STORE/NAME` and `ttasks queue workflow set QUEUE NAME:VERSION` as a hand-over on the task; never run them, and never build a workflow with the `image-creator` launcher |

A workflow-only change bumps no `image_version`; an `images/` change bumps no
`workflow_version`.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Rejecting a check with `111` | `111` is a check failure; reject with `112` and a `message` |
| Importing `../../development/scripts/pr_lib.py` | Copy what you need into this workflow's `scripts/` |
| `curl -H "Authorization: Bearer $TOKEN"` | Header on stdin via `curl --config -` |
| Keeping `0.1.0` for "just text" | Bump; same version with new content is refused |
| Adding status steps to an agent image's Flow table | Add a status, artifact or check to the workflow |
| Script without a test in `make check` | Add `tests/` and the Makefile line |
