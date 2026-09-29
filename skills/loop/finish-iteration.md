## Finishing this iteration

Only the root iteration owner may run `scripts/loop.sh done` (with or without `--idle`).
A subagent must never run `scripts/loop.sh done`; it must return its result to its parent.
This remains true even if the parent is unavailable, the subagent has no active
work, or the task asks it to finish.

This iteration runs unattended: no person reads or answers this session. A
turn that ends with text and no tool call stops the iteration until it times
out. Until `scripts/loop.sh done` has run, end every turn with a tool call:

- A status, a summary, or a reply to a harness reminder is text followed, in
  the same turn, by the next tool call.
- Never ask for missing information in text. Work from what you have, record a
  question where the owning skill records questions, or name the unknown in
  your final text, then make the next tool call.
- Your final text is followed, in the same turn, by `scripts/loop.sh done`.

A turn may end without a tool call only while a harness-tracked background
command or subagent is running; its completion notification resumes you.

After all current work, subagents, and terminal commands have finished, your
very last action MUST be `scripts/loop.sh done`. It closes this iteration, not the loop.
Use `scripts/loop.sh done --idle` only when the iteration did no useful work; plain
`scripts/loop.sh done` reports a productive iteration. Exiting without either form records
an incomplete iteration. Calling it twice is safe.

Durable commands launched through the packaged Scripts skill are the sole
exception: their result arrives in a later iteration, so they do not block
`scripts/loop.sh done`.
