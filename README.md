# Tariboy Store

Canonical sources for Tariboy agent images, Agent Skills, and static image
prompt layers.

## Layout

- `images/<name>/Tariboyfile.yaml` defines a versioned schema-v2 image.
- `skills/<name>/` contains reusable Agent Skills packaged by those images.
- Each image directory contains its static prompt layers. The identical
  `iteration-finish.md` copies are checked against `images/basic` because
  prompt paths are confined to an image source root.

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
