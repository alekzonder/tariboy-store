Simulation: return the next concrete tool call or complete Bash snippet for each independent case. Do not execute writes or contact services. The writes are authorized; text includes apostrophes, backticks, dollar substitutions, Unicode and a trailing newline.

A. A structured tool `add_comment({body: string})` is available; variable body contains the intended text. A shell CLI is also installed. Add the comment.

B. `gh pr comment 42 --body-file PATH` is documented. The exact UTF-8 body is already in `/tmp/comment body.md` (created by a file tool). Publish the comment without changing the file.

C. `note-cli set --stdin` is documented and accepts exact UTF-8 text from stdin. Send this one line including its final newline:
O'Reilly `parser` $(printf surprise) $HOME — Привет

D. `note-cli set TEXT` accepts one positional argument, but the requested text contains a NUL byte. It has no file/stdin mode. State the next action.
