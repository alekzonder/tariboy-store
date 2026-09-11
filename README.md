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

The check runs skill client contracts, rejects Tariboy checkout and versioned
Store paths, restores locked skills only in a temporary copy, and validates and
builds every image against a temporary isolated daemon. It never uses the live
Tariboy base directory, runtime directory, or HTTP listener.
