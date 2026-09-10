---
name: tasks
description: Use when claiming, decomposing, delegating, questioning, updating, or completing work in Tariboy Native Tasks.
---

# Native Tasks

This skill's launcher delegates to `ttasks`. The binary selects identity-bound
agent mode when `TARIBOY_TOOLS_SOCKET` is set; otherwise it uses operator mode.
The bare `tasks` command is an optional compatibility alias for `ttasks` in
agents whose image enables the `tasks` capability.

Execute requested actions when command execution is available. Otherwise,
return the exact `ttasks` sequence with placeholders for identifiers or
revisions returned by earlier commands; never substitute a future-tense promise
or prose summary.

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

For multiline shell arguments, assign a quoted heredoc to a variable, then
quote that variable. First choose a delimiter absent from every complete body
line; never reuse an example delimiter without checking the payload. Its
opening and closing delimiters start at column 1. This preserves Markdown
without executing body text or storing escapes:
If a requested delimiter collides, choose another and still return the full
command; do not stop at describing the risk.
Before publishing or proposing it, verify the same chosen delimiter opens once
and closes after the final payload line.
The quoted-heredoc recipe below is the only valid multiline form in a proposed
command; `$'...\n...'` is invalid even when a shell would expand its escapes.
When proposing rather than executing a write, show the variable assignment and
all consuming `ttasks` commands together; never claim a task was changed.

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

For a flexible task, ask with
`ttasks ask <key> user:<login>|agent:<name> <text>`.
A comment is not a blocking question.

For workflow-managed work, begin with
`ttasks work next --idempotency-key <stable-key>` and
`ttasks work show <assignment>`. Treat its packet as the complete authority:
use only declared actions, tools, outcomes, and channel patterns. Add artifacts
with `ttasks artifacts add <assignment>`, inspect assignment questions with
`ttasks questions <assignment>`, answer with `ttasks answer <question>`, and
subscribe with `ttasks observe subscribe <assignment> <pattern>`. Complete with an
allowed outcome. Raw channel subscriptions and undeclared direct or group
messages remain denied. Never invent another principal's identity.
