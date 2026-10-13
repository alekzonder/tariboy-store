---
name: workdir
description: Use when an agent needs the configured Tariboy workdir path for a command or file outside its current directory, puts a script, skill copy or temporary file there for a task, or finishes a task that left files there.
---

# Workdir

Only a literal `workdir: /absolute/path` runtime line in the current prompt
defines the configured path. A harness working directory, current directory,
Git, or environment variable does not. If the line is absent, request the path
and stop.

Resolve workdir-relative commands to absolute paths. For a Tariboy script
operation, respond with the resolved absolute path and: "Use the `scripts`
skill for this operation."

## Task files

Everything a task creates in the workdir lives under `WORKDIR/TASK-KEY/`:
outputs, logs, eval runs, state directories and helper scripts. Never write a
task file at the workdir root.

| Need | Action |
| --- | --- |
| An installed skill packages a script for the operation | Run it in place by its absolute path inside that skill's directory, with the arguments its `SKILL.md` documents. Never copy it or the skill into the workdir, rewrite it, or wrap it in a script of your own. |
| No packaged script covers the operation | Write the helper in `WORKDIR/TASK-KEY/`. |

## Cleanup at completion

Once the task is complete (`ttasks done KEY` or its final workflow outcome
succeeded), remove `WORKDIR/TASK-KEY/` with everything in it: helper scripts,
skill and Store copies, outputs, logs, eval runs and temporary files. Keep
only:

- paths the task recorded as kept, by name;
- the state directory of a Scripts definition that is still active, until the
  `scripts` skill removes that definition;
- every other task's files.

A completed task's evidence that the task did not record as kept is removed
too: its results belong on the task, not in the workdir.
