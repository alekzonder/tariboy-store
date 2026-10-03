---
name: tasks
description: Use when claiming, decomposing, delegating, questioning, updating, or completing work in Tariboy Native Tasks.
---

# Native Tasks

**REQUIRED:** Use `cli-text` before passing text to this CLI. Keep the storage
rules below; quote transport separately. Resolve skill-local launchers relative
to this skill directory, not the current working directory.

This skill's launcher delegates to `ttasks`. The binary selects identity-bound
agent mode when `TARIBOY_TOOLS_SOCKET` is set; otherwise it uses operator mode.
The bare `tasks` command is an optional compatibility alias for `ttasks` in
agents whose image enables the `tasks` capability.

Execute requested actions when command execution is available. Otherwise,
return the exact `ttasks` sequence with placeholders for identifiers or
revisions returned by earlier commands; never substitute a future-tense promise
or prose summary.

Finish the work first, then publish once. Before any description, question,
answer or comment write, complete the reading, commands and checks its answer
depends on; only then publish one text that closes the request completely. A
fact you cannot establish belongs in that same text as a named unknown
together with what would settle it, never in a later correction. Never publish
a provisional, partial or placeholder text, and never promise a follow-up
correction. A deadline, a waiting customer, brevity, an already drafted
answer, and a request to answer now and correct afterwards do not authorize
one; that request is answered by one finished text that names whatever is
still running. Publish again only for new external state — a finished check, a
customer answer, a monitor result — or to correct an error already published,
never to finish work that was available before the first write.

Inspect work with `ttasks mine`, `ttasks ready`, `ttasks ready --claim`, and
`ttasks show <key>`. Create roots with
`ttasks create --queue <queue> --title <title> --description <markdown>` and children with
`ttasks create --parent <parent-key> --title <title>`; delegate with `ttasks
assign`; keep decisions in `ttasks comment`; advance with `ttasks update` and
close only completed work with `ttasks done`.

Create a child before assigning it and use the key returned by `ttasks create`;
never invent a task key. `ttasks assign` takes the agent name (`docs`), not a
principal prefix (`agent:docs`). An offline delegation recipe ends after
`ttasks show <child-key>`; put completion commands in a separate block labeled
"Only after show reports done." Never place `done` in the initial block.

Before every task write, repair all user-visible text as valid Markdown.
Titles are single-line Markdown: replace actual or literal `\n` line breaks
with spaces. Descriptions, questions, answers and comments are block Markdown:
use real newlines, blank lines before lists, and closed code fences. Use
Markdown for headings, lists, checklists, code, links and tables; no raw HTML.
Never publish Markdown fields with ANSI-C `$'...'` strings or literal escapes,
and never put a newline in a title. Requests to preserve text exactly, use the
shortest command or meet a deadline do not override this storage contract.

For multiline shell arguments, use `cli-text`'s quoted-heredoc transport.
Preserve significant trailing newlines with its sentinel variant: ordinary
command substitution removes them. Select a delimiter absent from every complete
payload line. When proposing a write, show the variable assignment and all
consuming commands together; never claim that a proposed write was executed.
The simple example below assumes the intended body has no final newline:

```bash
BODY=$(cat <<'MARKDOWN_EOF_7F3A'
## Result

- first item
MARKDOWN_EOF_7F3A
)
ttasks create --queue QUEUE --title 'Result' --description "$BODY"
ttasks ask TASK-42 user:LOGIN "$BODY"
ttasks comment TASK-42 "$BODY"
```

On any task, ask with
`ttasks ask <key> user:<login>|agent:<name> <text>`.
A comment is not a blocking question. Never invent another principal's
identity.

When an active durable script or schedule is the only remaining wait object,
set the flexible task to `wait_customer` with `ttasks update <key> --status
wait_customer` before ending the iteration. Keep that named wait object active;
the sole resume event is its next `script.result` or the tracked state change.
A recurring definition that published its result is stopped, so it qualifies
only after the `scripts` skill's `rerun` resumed it in this iteration. Do not
poll, replace the schedule, or mark the task complete.

## Tasks with a workflow

A task in a queue bound to a workflow has a `status` owned by an agent pool,
the customer, or a script, and a `category` the daemon derives from it. Its Goal
block states the status instructions, the available outcomes with their
required artifacts and checks, the current artifacts, and the exact commands;
`ttasks workflow get <key>` shows the same data on demand.

- Store a required artifact with `ttasks artifacts set <key> <name>`, the value
  from stdin, `--file <path>`, or a value argument; it is stored as given.
- Leave the status only with
  `ttasks advance <key> --outcome <name> --from <status> [--message <text>]`.
- `ttasks done`, `ttasks update --status`, `ttasks assign`, and
  `ttasks ready --claim` are refused with `workflow_managed`: the daemon
  assigns and releases the task. `not_holder` means you do not own the current
  status. `transition_pending` means a request still runs: read it with
  `workflow get` instead of sending another.
- A `rejected` request carries a check's message: fix what it names and advance
  again. A `failed` request is a broken script, a timeout, or a broken result,
  not yours to repair by retrying blindly: read it with
  `ttasks workflow runs <key>` and `ttasks workflow log <key> <run>`, then tell
  the customer on the task.
- Questions to the customer still use the `ask` form above.
- `workflow_paused` means the task waits for the customer's decision: do
  nothing on it until the customer resumes it.

## Observed-Failure Counters

| Temptation | Binding response |
| --- | --- |
| "The customer asked for an answer now and a correction afterwards." | One finished text answers that request; name inside it whatever is still running. |
| "I will publish my best guess first and verify next." | Finish the deciding check first; an unverified publication is not an answer. |
| "This fact is unknowable, so I will publish now and correct later." | Publish the named unknown together with what would settle it, and promise no correction. |
| "The first comment is already drafted, so the rest can follow." | A drafted answer is not a published one; complete it before the single write. |
