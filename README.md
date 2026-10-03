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
tariboy image build official/tariboy-developer
```

For a local checkout:

```bash
tariboy store add local "$(pwd -P)"
tariboy image build local/basic
```

The default tag is the manifest's `image_version`. Update an existing source
with `tariboy image version update patch --path images/<name>` before publishing
changed content.

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
request's text. Run it with `official/tariboy-workflow-developer`, an agent
image with the tools that do the work and no process of its own: it works only
tasks of a workflow queue, and its `github-pr-workflow` skill proves GitHub
access and finds or creates the task's one pull request without a monitor.
`official/tariboy-developer` also works such tasks, beside its own process for
tasks without a workflow.

## Daemon version

This Store needs a daemon with workflow images and `TARIBOY_QUIET_EXIT`:
Tariboy 0.72 or later. Its scripts exit `111` when nothing changed, and its
`workflows/` sources build only on such a daemon; an older daemon does not
treat that exit as quiet.

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
