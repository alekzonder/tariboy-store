# Loop completion regression

Case 4 was run as a read-only text simulation with fresh Codex actors using
`gpt-5.6-terra`, reasoning effort `medium`, and `fork_turns: "none"`. The
actors received the exact case prompt and complete `finish-iteration.md`; the
rubric and other run were withheld. No live iteration was completed.

- Eval fixture SHA-256: `16eb7040aae732657860ad9a20e2fc9030e0639546c7e46503ed353afc93a1fa`
- Baseline prompt SHA-256: `2cd8899318282264671dc4afb8c68cba5e311a870fe6e91e268b75292b424039`
- Candidate prompt SHA-256: `320261a2d850917a90519df43fcb7034fa4595f229f8290e87ff41d55e91aa77`

| Variant | Repetition | Actor response | Manual result |
| --- | ---: | --- | --- |
| Baseline | 1 | Productive: `i-am-done`; idle: `i-am-done --idle`. | Fail |
| Baseline | 2 | Productive: `i-am-done`; idle: `i-am-done --idle`. | Fail |
| Baseline | 3 | Productive: `i-am-done`; idle: `i-am-done --idle`. | Fail |
| Baseline | 4 | Productive: `i-am-done`; idle: `i-am-done --idle`. | Fail |
| Baseline | 5 | Productive: `i-am-done`; idle: `i-am-done --idle`. | Fail |
| Candidate | 1 | Productive: `scripts/loop.sh done`; idle: `scripts/loop.sh done --idle`. | Pass |
| Candidate | 2 | Productive: `scripts/loop.sh done`; idle: `scripts/loop.sh done --idle`. | Pass |
| Candidate | 3 | Productive: `scripts/loop.sh done`; idle: `scripts/loop.sh done --idle`. | Pass |
| Candidate | 4 | Productive: `scripts/loop.sh done`; idle: `scripts/loop.sh done --idle`. | Pass |
| Candidate | 5 | Productive: `scripts/loop.sh done`; idle: `scripts/loop.sh done --idle`. | Pass |

The matched repetitions reproduce the supplied iteration failure without
variance and check the corrected command selection. They do not exercise the
live daemon.
