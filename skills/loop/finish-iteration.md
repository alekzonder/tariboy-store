## Finishing this iteration

Only the root iteration owner may run `scripts/loop.sh done` (with or without `--idle`).
A subagent must never run `scripts/loop.sh done`; it must return its result to its parent.
This remains true even if the parent is unavailable, the subagent has no active
work, or the task asks it to finish.

After all current work, subagents, and terminal commands have finished, your
very last action MUST be `scripts/loop.sh done`. It closes this iteration, not the loop.
Use `scripts/loop.sh done --idle` only when the iteration did no useful work; plain
`scripts/loop.sh done` reports a productive iteration. Exiting without either form records
an incomplete iteration. Calling it twice is safe.

Durable commands launched through the packaged Scripts skill are the sole
exception: their result arrives in a later iteration, so they do not block
`scripts/loop.sh done`.
