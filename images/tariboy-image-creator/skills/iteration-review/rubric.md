# Rubric `iteration-review/1`

You assess one evidence pack: one iteration of another agent, or one task
after `done`. You only read the pack and write one JSON object. You run no
command and change no file other than the output file you were given.

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

## Task assessment

A task pack (`# Task pack KEY`) gets `task_key` and no `iteration_id`. Its
`task_fit` `note` names the time from creation to done, the number of rework
rounds and the number of questions to the customer, taken from `## Measures`.
Use the iteration assessments listed in the pack as evidence of the process.

## Output

Write exactly this shape to the output file. No other fields.

```json
{
  "rubric_version": "iteration-review/1",
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
