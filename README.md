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
Behavioral evidence and executable text checks are in `skills/cli-text/evals/`;
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

`official/tariboy-workflow-developer` is the older image for workflow tasks
only. It stays in the Store without changes while agents move to
`official/developer`. A separate change removes it two weeks after the last
agent moves, if no agent moves back.

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

## Checks

Requirements: Bash, GNU Make, Python 3, Git, ripgrep, Node.js/npm, and matching
`tariboy` plus `tariboyd` binaries on `PATH`. Override the binaries with
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

The check also fails when an image or a workflow has no `ROLE.md`, an empty
`ROLE.md`, or a `ROLE.md` of more than 500 characters. Two images have no
`ROLE.md` because they will be removed: `llm-as-judge` and
`tariboy-workflow-developer`.
