# CLI text evals

**REQUIRED:** use `authoring-evals` before you change a case or start a run.
Run results go to the run workspace in the configured workdir. Do not commit
them here.

## Behavioral cases

`evals.json` holds six cases. Each case gives its input in `prompt`, or
names a fixture script in `fixture`:

| Case | Input | What the evaluator observes |
| --- | --- | --- |
| `comment-argument-only` | `fixtures/cli-sandbox.sh stubs` | the `ttasks comment` call in `records.json` |
| `commit-message` | `fixtures/cli-sandbox.sh git` | `git log -1 --format=%B` in the sandbox |
| `pull-request-body` | `fixtures/cli-sandbox.sh stubs` | the `gh pr create` call in `records.json` |
| `javascript-exec-argument` | `prompt` only | the returned JavaScript, run against a recording `note-cli` stub |
| `owning-skill-proposals` | `fixtures/owning-skills.sh` | the four snippets, run with `bash` in the fixture directory, and the argv in `calls.jsonl` |
| `input-modes` | `prompt` only | the four proposed calls, run against stubs with the same interfaces |

The runner sets `EVAL_DIR` to an empty case directory, runs the fixture
script with the case `args`, and starts the actor in that directory. The
fixture scripts write only inside `EVAL_DIR`. `owning-skills.sh` copies
`SKILL.md` of `tasks`, `context`, `mail` and `status` from the revision under
test and replaces each launcher with a recording stand-in. No case calls a
daemon, a task, a mailbox or GitHub.

The actor gets the `cli-text` skill and the case `prompt`. The actor never
gets `expected_output`. In every case, the evaluator compares the text that
the CLI received with the requested text byte for byte. The evaluator also
reads the tool calls of the actor for a `bash -lc`, `bash -c`, `sh -c` or
`eval` wrapper.

## Deterministic checks

`make check` runs these two checks. They need Python 3, Node.js and Bash, use
recording CLI stubs in temporary directories, and pass a minimal environment
without credentials:

```bash
python3 -B skills/cli-text/evals/check-text.py
python3 -B skills/cli-text/evals/check-shell-layer.py
```

`check-text.py` reads the JavaScript example from `SKILL.md` at run time. It
runs the example on seven inputs that the script holds: special characters,
empty text, a line equal to the delimiter of the example, CRLF, no final
newline, only newlines, and NUL. The stub must receive each text byte for
byte. For NUL, the example must stop before it calls the CLI.

`check-shell-layer.py` replays the mechanism of the DEV review failures. The
quoted heredoc recipe inside `bash -lc '...'` must lose the text. The same
recipe at the top level, or a file that the file tool wrote, must keep the
text byte for byte.

These checks run code. They do not show how a model behaves. A change to
`SKILL.md` needs new actor runs of the behavioral cases.
