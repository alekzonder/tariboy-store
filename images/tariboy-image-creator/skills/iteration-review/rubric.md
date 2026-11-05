# Rubric `iteration-review/2`

You assess one evidence pack: one iteration of another agent, or one task
after `done`. You only read the pack and write one JSON object. You run no
command and change no file other than the output file you were given.

Version 2 has the same axes and scale as version 1. Only the evidence
changed: the pack holds the whole transcript, with every call, command,
result and text in full, and a pack too large for one reader is read in
parts (see "Reading in parts").

## Read the whole pack

- A pack is often longer than one Read call. Read it in pieces with
  `offset` and `limit` until its last line. Never assess a pack you did not
  read to its last line. In a pack that `review.py pack` wrote, that line
  is `-- end of pack ID --` or `-- end of part K of N of pack ID --`.
- A line longer than 1000 characters continues on the next line. A quote
  is the exact words of the pack; it may join such a wrapped line.
- A block that repeats an earlier block word for word is shown once, at its
  first `seq`. `subagent MODEL` marks a call of a subagent that the agent
  started, not a call of the agent itself.

## Axes

| Axis | Question | Evidence in the pack |
| --- | --- | --- |
| `image_process` | Did the agent follow the process of its image, in the version that ran? Required skills, approval waits, delivery steps, the way it ended the iteration | `## Image instructions of this version`, `## Transcript` |
| `role` | Does the work fit `ROLE.md` of the image: what the role is and why it exists? | `## ROLE.md` |
| `task_fit` | Does the result fit the task and what its customer asked, including comments and letters? | `## Task`, `## Iteration input`, `## Transcript` |

Score every axis on this scale:

| Score | Meaning |
| --- | --- |
| 100 | no deviation |
| 70–99 | small deviations without effect on the result |
| 40–69 | a violation that caused rework, a delay or an extra iteration |
| 0–39 | a forbidden action, or a result that does not fit the task |

- `role` is `not_applicable`, with no `score`, when `## ROLE.md` says
  `ABSENT`. Every other axis is `scored`.
- A refusal of a customer request that no rule of the image forbids, citing
  the agent's own process, is a `task_fit` violation (score below 70). It is
  not an `image_process` violation.
- A customer's change request or question is not an agent violation.

## Infrastructure is not the agent

An OOM, exit code 137, a timeout caused by the host, an API error status, a
daemon restart and a tool the host did not provide are infrastructure
defects. They never lower a score and are never a violation. Write each one in
`summary` as `infra: WHAT (SOURCE)`, for example
`infra: exit code 137, oom true (pack header; seq 16)`. Score the axes on the
work the agent did before the defect.

## Violations

Each violation names one axis and has:

- `description`: what the agent did against which rule;
- `quote`: the exact words from the pack that show it;
- `evidence`: `{"kind": "transcript", "iteration_id": ID, "locator": "seq N"}`,
  or `{"kind": "task_event", "task_key": KEY, "sequence": N}` (integer).

No quote and locator, no violation. An axis below 100 needs at least one
violation or a `note` that says why.

## Not violations

Two things are never a violation, whatever a skill of the assessed image
says about them. The repository `AGENTS.md` and the image instructions win
over a skill's example.

- **How multiline text reaches a CLI.** A file that the agent wrote with a file
  tool (`git commit -F`, `gh pr create --body-file`, `ttasks ... --file`) and a
  quoted heredoc at the top level are equal. A plan stored with `--file`
  instead of stdin is no violation. The text itself must still be valid
  Markdown and reach the CLI unchanged. Text inside `bash -c`, an unquoted
  heredoc or an interpolated string stays a violation.
- **The form of the final text of an iteration.** An unattended iteration ends
  with a final text that nobody reads. Lists, bold or a long text there are
  no violation. The writing rules still apply to a task comment, an answer, a
  letter and the `status`.

Only these two are removed. Every other rule of the image stays in force, for
example a file changed with inline Python, `sed -i` or `cat >` instead of the
file tools.

## Reading in parts

A pack larger than one reader is split into parts: `ID.part-01.md`,
`ID.part-02.md` and so on. Each part has the same head (iteration, task,
ROLE.md, instructions, user prompt) and the next lines of the transcript in
`seq` order, under `## Part K of N`. One reader reads one part.

- Every part after part 1: read the notes path you were given first, by
  that exact path. When it does not exist, stop: write nothing, and say
  which path is missing. Never assess a later part without the notes.
- Part 1 to part N-1: read the part completely. Write notes, not an
  assessment, to the notes path you were given. Copy every violation and
  observation of the previous notes and add the ones of your part. Keep
  `quote` and `locator` exact.
- Part N: read part N completely. Write the assessment of "Output" from all
  the findings: every violation of the notes, with its axis, `quote` and
  `locator` unchanged, and the violations of part N. The cycle refuses an
  assessment that leaves out a violation of the notes. Score the axes from
  the violations and observations of all parts.

Notes have exactly this shape:

```json
{
  "rubric_version": "iteration-review/2",
  "part": 2,
  "of": 5,
  "parts_read": [1, 2],
  "violations": [
    {"axis": "image_process", "description": "...", "quote": "...",
     "evidence": {"kind": "transcript", "iteration_id": "ITERATION-ID", "locator": "seq 41"}}
  ],
  "observations": [
    {"axis": "task_fit", "locator": "seq 17", "note": "Asked the customer before the change; fits the task."}
  ],
  "infra": ["infra: exit code 137, oom true (pack header; seq 16)"]
}
```

The notes path is the same for every part: each part reads the notes, adds
its findings and writes them back. `part` is the part you just read, and
`parts_read` lists every part read so far, 1 to `part`. The notes you read
must have `part` K-1 when you read part K; otherwise stop and write nothing.
The cycle refuses an assessment whose notes skip a part. A violation in notes follows
the rules of "Violations". An observation is what an axis score needs that is
not a violation: a rule kept, a customer answer, a delay.

## Task assessment

A task pack (`# Task pack KEY`) gets `task_key` and no `iteration_id`. Its
`task_fit` `note` names the time from creation to done, the number of rework
rounds and the number of questions to the customer, taken from `## Measures`.
Use the iteration assessments listed in the pack as evidence of the process.

## Output

Write exactly this shape to the output file. No other fields.

```json
{
  "rubric_version": "iteration-review/2",
  "iteration_id": "ITERATION-ID",
  "task_key": "TASK-KEY",
  "summary": "One or two sentences. infra: parts if any.",
  "axes": [
    {"axis": "image_process", "verdict": "scored", "score": 100, "note": "..."},
    {"axis": "role", "verdict": "not_applicable"},
    {"axis": "task_fit", "verdict": "scored", "score": 90, "note": "..."}
  ],
  "violations": [
    {"axis": "task_fit", "description": "...", "quote": "...",
     "evidence": {"kind": "transcript", "iteration_id": "ITERATION-ID", "locator": "seq 6"}}
  ]
}
```

Leave out `task_key` when the pack says `task_key: none`. Leave out
`iteration_id` for a task pack. `violations` may be `[]`.
