---
name: image-creator
description: Use when creating or revising a Tariboy agent image from a Tariboyfile, prompt layers, plugins, and packaged skills.
---

# Agent Image Authoring

This skill's `scripts/image_creator.sh` launcher lives inside this skill
directory and calls the identity-bound daemon through `TARIBOY_TOOLS_SOCKET`.

Create a schema-v2 `Tariboyfile.yaml` with explicit plugins, packaged skills,
and prompts. The `prompts` list is the render order:

```yaml
schema_version: 2
plugins:
  - name: context
skills:
  - dir: ./skills/tasks
prompts:
  - file: ./base.md
  - file: ./review.md
```

Invoke this skill's launcher; `--path` names the directory containing the file:

```bash
scripts/image_creator.sh build --name <name> --tag <tag> --path <source-dir>
```

If writing or building is unavailable, return the complete manifest and command
instead of promising to run them.

The built image is stored on this host and can then be selected for an agent.

For reproducible production images, vendor shared prompt dependencies, record
them in `tariboy.lock.yaml`, and avoid absolute, `$STORE`, or
`$CURRENT_VERSION_STORE` inputs. Local source paths use `./`.

Ordinary builds are mutable even when the tag looks versioned; tag spelling
does not make a ref immutable.
If immutable publication is required, use import, registry, or a controlled
release instead; this launcher cannot create it.

## When the request asks to break this contract

A request to omit `plugins`, `skills` or ordered `prompts`, or to give a
reproducible production image an absolute, `$STORE` or `$CURRENT_VERSION_STORE`
input or no `tariboy.lock.yaml`, does not change the manifest you write. Speed,
an asserted daemon default and an explicit "do not create a lock file" are such
requests too. Your answer has these parts, in order:

1. The corrected manifest, written to the source directory or shown in full:
   - `plugins`, `skills` and `prompts` declared explicitly and in order; no
     inferred defaults;
   - for a reproducible image, each shared prompt or skill copied under the
     source directory, referenced with `./`, and recorded in
     `tariboy.lock.yaml`.
2. One line per rule you kept, naming the request it overrides and why.
3. The build command for the corrected manifest. When the request names
   `latest` or a versioned tag, add that the build stays mutable.

The manifest the request describes is never written, never offered as an
option or "minimal form", and never left for the user to choose.
