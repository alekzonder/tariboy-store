# Tariboy Store

Canonical sources for Tariboy agent images and Agent Skills.

## Layout

- `images/<name>/Tariboyfile.yaml` defines a versioned schema-v2 image.
- `skills/<name>/` contains reusable Agent Skills packaged by those images.
- `skills/loop/finish-iteration.md` is the shared finishing prompt.

Every image uses repository-relative paths. A built runnable image contains its
declared static prompt bytes and complete Agent Skill trees; it does not need
this checkout at runtime. Dynamic runtime placeholders and plugin capabilities
remain implemented by the destination `tariboyd`, which validates them during
build and activation.

## Register and build

Register this Git repository on the selected daemon, refresh it, then build an
image by its Store selector:

```bash
tariboy store add official git@github.com:alekzonder/tariboy-store.git
tariboy store refresh official
tariboy image build official/basic
tariboy image build official/developer
```

For a local checkout:

```bash
tariboy store add local "$(pwd -P)"
tariboy image build local/basic
```

The default tag is the manifest's `image_version`. Update an existing source
with `tariboy image version update patch --path images/<name>` before publishing
changed content.

## ROLE.md

`ROLE.md` is the customer's text that says what a role is and why the image or
workflow exists. It is a file next to the manifest:

- `images/<name>/ROLE.md`, next to `Tariboyfile.yaml`;
- `workflows/<name>/ROLE.md`, next to `Workflowfile.yaml`.

A `ROLE.md` in this Store obeys these rules:

- The file is Markdown in UTF-8 and the text is in English.
- The file has 500 characters or fewer. Count the characters with `wc -m`.
- The text says only what the role is and why the image or workflow exists.
- The text does not describe the work format, the process, the skills, the
  commands or the rules. The instructions, skills and status instructions
  already describe them.
- The text has no draft mark, such as "Draft. The customer approves."

Only the customer writes and approves `ROLE.md`. An agent prepares a draft and
puts in the approved text without changes. The agent prompt does not include
`ROLE.md`. The daemon only adds the file to the image manifest and shows it.

A build does not need `ROLE.md`: an image or workflow without it builds. In
this Store, every image and every workflow must have a `ROLE.md` after the
customer approves it.

The image creator follows these rules for each image and workflow:

1. Read `ROLE.md` before a change.
2. Compare `instructions.md`, the skills, the status instructions and the evals
   with `ROLE.md`.
3. Do not change or create `ROLE.md` without the customer's approval.
4. Do not copy all of `ROLE.md` into `instructions.md`, a skill or a status
   instruction.
5. If a request contradicts `ROLE.md`, ask a question on the task. Do not
   change `ROLE.md`.

## CLI text in every image

Every image packages `skills/cli-text` and loads its `cli-text.md` before role
instructions. Keep both declarations when creating new images:

```yaml
skills:
  - dir: ../../skills/cli-text
prompts:
  - file: ../../skills/cli-text/cli-text.md
```

The skill covers CLI comments, context, messages, status and generated text,
including JavaScript-to-shell calls. Owning skills retain their formatting and
lifecycle rules. No additional CLI or dependency is required.

External Stores must copy the skill directory and adapt both relative paths.
Rebuild and select the updated image for agents to receive these instructions;
existing image digests and images maintained elsewhere do not change automatically.
Behavioral cases and executable text checks are in `skills/cli-text/evals/`;
per-image routing evidence is in each image's `evals/cli-text/` directory.

## Writing style in every image

Every image packages `skills/writing-style` with the two language skills it
names, and loads its `writing-style.md` right after `cli-text.md`. The skill
covers text for people: task text, letters, `status` and documentation. It
selects the language of the question or of the changed document, applies
`simple-english` to English text and `simplified-technical-russian`
(`loadkpi/simplified-technical-russian-skill`) to Russian text, and keeps the
brevity rules short. Install all three with `npx skills add` and declare them:

```yaml
skills:
  - dir: ./.agents/skills/writing-style
  - dir: ./.agents/skills/simple-english
  - dir: ./.agents/skills/simplified-technical-russian
prompts:
  - file: ./.agents/skills/cli-text/cli-text.md
  - file: ./.agents/skills/writing-style/writing-style.md
```

`scripts/check-writing-style.py`, part of `make check`, fails when an image
misses one of these entries. Code, commit messages and pull request text are
outside the skill. Its behavioral cases are in `skills/writing-style/evals/`.

## Workflow images

A workflow image packages a task workflow: the statuses a task moves through,
who owns each one, and the scripts that check or watch for a transition. It is
built from `workflows/<name>/`:

- `Workflowfile.yaml` is the manifest (`schema_version: 1`).
- `statuses/<status>.md` holds the instructions an agent reads in a status.
- `scripts/` holds the check and watch scripts the manifest names.

A workflow source directory is self-contained: no symlinks, no path outside the
directory, every script executable, and no file named `manifest.json` at its
root. Scripts use only the Python 3 standard library, `curl`, `git` and POSIX
`sh`.

An agent image holds the tools, skills and prompts of one agent. A workflow
image holds the process around a task: statuses, transitions, required
artifacts and their scripts. Nothing of the process belongs in an agent image,
and no agent tooling belongs in a workflow image.

Build one by its Store selector, or from a path:

```bash
tariboy workflow build --source official/research
tariboy workflow build --path workflows/research
tariboy workflow validate --path workflows/research
```

The default tag is the manifest's `workflow_version`. Update an existing source
with `tariboy workflow version update patch --path workflows/<name>` before
publishing changed content.

Bind a built workflow to a queue with the operator command:

```bash
ttasks queue workflow set QUEUE research:0.1.0
```

The `research` workflow runs on any agent image with the `tasks` plugin, for
example `official/basic`.

The `development` workflow holds the whole development process: planning,
approval, implementation, the pull request watch and cleanup, and its checks
prove the plan's sections, the branch, the verified head commit and the pull
request's text. Run it with `official/developer`.

A task of a queue bound to the `development` workflow starts in `backlog`, a
status the customer owns: no agent takes it until the customer starts it with
`ttasks advance KEY --outcome start --from backlog`, which moves it to `plan`.

The `pr-review` workflow reviews pull requests. Its source `pull-requests`
polls every repository named in the queue secret `REVIEW_REPOSITORIES`
(`owner/repo` entries separated by commas; one repository is written
`owner/repo,`, because the daemon hides a queue secret's exact value in task
keys and artifacts) every two minutes and creates one task per open, non-draft
pull request, keyed `owner/repo#N`. A reviewer writes the review in `review`;
the customer then publishes it, sends it back with `revise`, or closes the task
in `approval` (findings) or `approval_clean` (none); `publish` posts the
approved review on GitHub as one `COMMENT` review. Run it with
`official/reviewer`, an agent image with no process of its own and no
`scripts` capability, whose `pull-request-review` skill fetches, checks and
publishes reviews. The queue needs the secrets `GITHUB_TOKEN` and
`REVIEW_REPOSITORIES`; the reviewer agents need `GITHUB_TOKEN` in their own
environment to publish.

The `image-improve` workflow takes an improvement of an image, workflow or skill
from the reviewer's triage task to a published image. A task starts in `triage`,
which the `image-creators` pool owns. The image creator checks the task for a
duplicate, the route and noise, and applies the rule `Change without approval`:

| Status | Owner | Outcomes |
| --- | --- | --- |
| `triage` | pool `image-creators` | `needs_approval` to `approval`, `autonomous` to `implement`, `close` to `closed` |
| `approval` | customer | `approved` to `implement`, `changes_requested` to `triage`, `rejected` to `closed` |
| `implement` | pool `image-creators` | `ready` to `deliver` |
| `deliver` | pool `image-creators` | `submitted` to `merge` |
| `merge` | script | `merged` to `publish`; `rework`, `changes_requested`, `conflict`, `closed_unmerged` to `implement` |
| `publish` | pool `image-creators` | `published` to `done` |

The checks stop a task that skips a step. `triage-check.py` compares the triage
record with the outcome. `evals-check.py` rejects `ready` without an `evals`
artifact, or when a new or changed scenario has no base and new result, when
new passes fewer than 2 of 3 runs, or when new is worse than base.
`pr-open.py` needs one open pull request from the branch at the verified
commit. The `merge` watch waits for the customer's merge. With the queue env
var `AUTO_MERGE=true` it merges the pull request itself once the verified head
is mergeable and every check and commit status of it succeeded;
`AUTO_MERGE_WITHOUT_CHECKS=true` also lets it merge a head without any check,
for a repository without CI. `published-check.py` rejects `published` unless each image has its
version tag and `latest` under one full digest in the `publication` artifact,
and each merged workflow has its version. The check cannot read the registry,
so the customer confirms the record with `tariboy image ls`.

Create the tasks in a queue bound to the workflow without an assignee: the
daemon gives each task to the pool. Run the pool with `tariboy-image-creator`
in mode `workflow`. The reviewer's triage creates such tasks in `IMPROVE`.

### Workflow evals

A workflow eval case tests the instructions of one status. The runner puts one
task into that status, runs one real iteration of the actor image on the real
Goal block, and then checks the result with scripts. No model judges the
result.

A case is an entry in `workflows/<name>/evals/evals.json` that has a `status`
field. An entry without `status` is a case that describes a scenario in words,
and the runner skips it. A workflow case has these fields:

| Field | Content |
| --- | --- |
| `id` | Lowercase words joined by hyphens |
| `status` | A status that an agent pool owns |
| `actor` | `{"image": "developer", "model": "haiku"}`. `model` and `effort` are optional |
| `task` | The `title` and `description` of the task |
| `fixture` | `{"script": "evals/fixtures/<file>.sh", "args": [...]}`, the script that creates the repository of the actor |
| `path` | The steps that bring the task from `backlog` to `status` |
| `criteria` | The checks that the run must pass |
| `prompt`, `expected_output` | The scenario and the success criteria in words, as for every eval |
| `timeout_s` | Optional limit for the iteration, in seconds |
| `secrets` | Optional queue secrets that the workflow requires, as `{"NAME": "value"}`. The runner sets `GITHUB_TOKEN` itself |

The fixture script writes only inside `$EVAL_DIR`. It creates the repository
of the actor in `$EVAL_DIR/repo`, the state of the fake GitHub in
`$EVAL_GITHUB_STATE`, and a JSON object of values in `$EVAL_VARS`. The `task`,
`path` and `criteria` fields can use these values as `${name}`. The
`development` fixture `widget-repo.sh` gives the variants `plain`,
`branch-pushed`, `pr-open`, `pr-merged` and `pr-diverged`. In `branch-pushed`,
another agent pushed one partial commit to the task branch, and only origin
keeps that branch. The `pr-review` and `research` cases use the same fixture.

A `path` step is one of these:

- `{"move": "STATUS"}` moves the task as the operator.
- `{"artifact": ["NAME", "VALUE"]}` sets an artifact.
- `{"advance": {"outcome": "...", "from": "...", "message": "..."}}` declares an outcome as the customer.
- `{"comment": "TEXT"}` adds a comment as the customer.
- `{"wait_status": "STATUS"}` waits until a watch script moves the task.

After the iteration, the runner checks these `criteria`:

- `status`: the status of the task.
- `outcome`: `{"name": ..., "state": "applied"}`, the last outcome that the actor declared.
- `no_outcome`: outcomes that the actor must not declare.
- `artifacts`: per artifact, `headings`, `contains`, `matches` (a regular expression), `equals`, `changed` or `absent`.
- `question`: `true` if the actor must ask the customer through the task, `false` if it must not.
- `comments`: `labels` that one comment of the actor must contain, `contains` text, or `worktree_path: true`, which needs each linked worktree named by its absolute path or its path relative to the main checkout.
- `repo`: the main checkout after the iteration: `branches`, `branches_include`, `worktrees`, `min_worktrees`, `clean`, `main`, `head` (the branch the main checkout has checked out; a detached HEAD fails), `head_checkouts` (how many times the main checkout switched branch, also when it switched back), `main_updated_only_by` (a list of prefixes: every reflog entry of the local `main` must start with one, for example `["commit", "merge", "pull"]`, so `branch -f`, `reset` and `update-ref` fail), `main_contains`, `origin_branches_include`. For origin: `origin_branches` (the exact list), `origin_branch_count`, and `origin_contains`, a list of `[BRANCH, SHA]` pairs, where each origin branch must contain the commit.
- `commands`: `absent`, a list of regular expressions that no shell command of the actor may match. The runner reads the commands from the actor's transcript, so the prompt text does not count. Use it for a forbidden way to do a step, such as an inline write to a file.
- `skills_first`: a list of skill names. The actor must open each one with the Skill tool before its first call of any other tool (a command, a file read or an edit). The runner reads the calls from the actor's transcript.
- `pulls`: the pull requests of the fake GitHub: `count`, `heads` (the exact list of head branches), `head_artifact` (each head equals this artifact), and `reviews` (the number of reviews published on them).

The runner starts its own `tariboyd` with a new base directory and a new
runtime directory, a Unix socket and no HTTP listener. It stops if that daemon
has agents or queues other than the default `TASK` queue. It never touches the
live daemon. It replaces GitHub with a fake: the actor reaches it through
`TARIBOY_GITHUB_CURL_BIN`, and the scripts of the workflow reach it through
their `GITHUB_API_URL` test seam. The fake reads the heads of pull requests
from a local bare repository, which is the `origin` of the fixture repository.

Run the cases of a workflow:

```bash
make workflow-eval WORKFLOW=development
make workflow-eval WORKFLOW=development ARGS='--case plan-new-task --repeat 3'
python3 scripts/workflow-eval.py --workflow development --model sonnet
python3 scripts/workflow-eval.py --workflow development --case complete-squash-merge \
  --status-override complete=/path/to/changed-complete.md
```

The default model is `haiku`. Each run of a case starts an agent and spends AI
budget. The runner prints `PASS` or `FAIL` for each run, each criterion with
its detail, the cost of each run and the total cost. It keeps the records of
each run in the directory that `--out` names, or in a new temporary directory:
the prompt with the Goal block, the transcript, the task state and the request
log of the fake GitHub. It exits with 0 when every run passes and 1 when a run
fails. `--status-override STATUS=FILE` replaces a status instruction in the
evaluated copy only. Use it to test a changed instruction before you commit it,
or to show that a case fails on a broken instruction.

Run the cases of a workflow before you publish a changed workflow. The
`tariboy-workflow-authoring` skill requires this run.

## Developer modes

`official/developer` is one image for the three iteration modes of the
daemon. Each mode has its own skill in the image:

| Mode | Iteration | Skill |
| --- | --- | --- |
| `workflow` | The goal task follows a workflow. The status instructions set the process. | `developer-mode-workflow` |
| `flexible` | The goal task has no workflow. The skill sets the process: plan, approval, one pull request, its monitor and completion. | `developer-mode-flexible` |
| `request` | No goal task. The agent answers the one-shot instruction or the letters, and records a change request as a task in the queue that the request names. | `developer-mode-request` |

The agent reads its mode from the daemon line `` Iteration mode: `NAME`. `` in
the `# Task Processing Order` block. That line wins over the Goal block. If the
line is not in the prompt, the agent uses the Goal block: a workflow task is
`workflow`, a task without a workflow is `flexible`, and no goal task is
`request`.

## Image creator modes

`official/tariboy-image-creator` is one image for two iteration modes. Each
mode has its own skill in the image:

| Mode | Iteration | Skill |
| --- | --- | --- |
| `workflow` | The goal task follows a workflow, for example a task of the `IMPROVE` queue bound to `image-improve`. The status instructions set the process. | `image-creator-mode-workflow` |
| `flexible` | The goal task has no workflow, for example a task of the `TASK` queue. The skill sets the process: plan, approval, one pull request, its monitor and completion. | `image-creator-mode-flexible` |

The agent reads its mode from the daemon line `` Iteration mode: `NAME`. `` in
the `# Task Processing Order` block. That line wins over the Goal block. If the
line is not in the prompt, the Goal block decides. The review cycle is part of
`instructions.md` and runs in either mode.

## Daemon version

This Store needs a daemon with workflow images and `TARIBOY_QUIET_EXIT`:
Tariboy 0.72 or later. Its scripts exit `111` when nothing changed, and its
`workflows/` sources build only on such a daemon; an older daemon does not
treat that exit as quiet. The `development` and `pr-review` workflows also
describe each check, watch and source with a `description`, which the task
panel and the agent's Goal block show; that field needs a daemon after
Tariboy 0.88.0, and an older one refuses the manifest with `description` as
an unknown field.

## Release publisher

`tariboy-release-publisher` creates a TARI task for each new release, proposes
a SemVer version and CHANGELOG entry for approval, then uses the target
repository's version script in an isolated worktree. It integrates into main
without a PR and verifies the annotated tag, release workflow and artifacts
before closing the task. Supply the repository and customer at launch.

## Eval suites

Each image, skill and workflow keeps its eval cases in `evals/evals.json`.
The `authoring-evals` skill, section "Fixtures and run results", gives the
rules. In short:

- Commit the input data of a case next to `evals/evals.json`: a file under
  `evals/files/`, or a script `evals/fixtures/NAME.sh` that creates data
  derived from the Store or code at run time. Put small textual state into the
  case `prompt`.
- Keep one copy of each fixture. Another suite names the same file by its
  relative path.
- Do not commit run results: actor responses, grading, logs, `results.json`,
  baseline and candidate outputs. They stay in the run workspace in the
  workdir.
- Do not commit large binary data.

## Checks

Requirements: Bash, GNU Make, Python 3, Git, ripgrep, Node.js/npm, and matching
`tariboy`, `tariboyd` and `tscripts` binaries on `PATH`. Override the binaries with
`TARIBOY_BIN` and `TARIBOYD_BIN`.

```bash
make check
```

The check runs skill client contracts, checks the image creator's closure-monitor
contract against a fake Scripts launcher, rejects Tariboy checkout and versioned
Store paths, restores locked skills only in a temporary copy, and validates and
builds every image against a temporary isolated daemon. It then validates and
builds every `workflows/<name>/Workflowfile.yaml` against the same daemon and
scans workflow manifests, scripts and status instructions for the same
forbidden paths. A workflow that fails validation fails the check and prints
the daemon's error list. The check never uses the live Tariboy base directory,
runtime directory, or HTTP listener.

The check also runs `scripts/check-skills-lock.py`. It recomputes the hash of
every `sourceType: local` skill in each `images/*/skills-lock.json` and fails
when a `computedHash` is stale. The automatic Store build refuses an image with
a stale hash (`skills_lock_mismatch`). After a change to `skills/NAME` or to an
image-local skill, run `npx skills experimental_install` in each consuming
image directory and commit the new `skills-lock.json`.

The check also fails when an image or a workflow has no `ROLE.md`, an empty
`ROLE.md`, or a `ROLE.md` of more than 500 characters. One image has no
`ROLE.md` because it will be removed: `llm-as-judge`.

The check also runs `scripts/check-evals.py` on the files that Git tracks.
It fails on a file in `evals/files/` or `evals/fixtures/` that no case or
fixture script names, on a case that names a missing file, on a file whose
content is the same as a file of another suite, and on a run-result file in
`evals/`. `scripts/check-evals-known.txt` lists the violations that existed
when the check was added. The list only shrinks: a new violation fails the
check, and a line whose violation is gone fails it too. Remove the line in the
change that fixes the violation.

The check also tests the workflow eval runner and runs it with
`--render-only` for every workflow. This mode runs no model and costs nothing:
the actor uses the `stub` harness from `scripts/workflow_eval/`. It brings each
case to its status and makes sure that the prompt carries the Goal block of
that status. A broken fixture or `path` fails the check. The run with a model
is `make workflow-eval`, which is not part of the check.
