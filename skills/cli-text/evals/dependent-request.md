This is a command proposal exercise. Read the four supplied skills, then give four independent complete Bash snippets; do not execute them. All writes are authorized in a disposable fixture; each CLI takes the text argument documented by its owning skill. Use the skill-local absolute launcher paths. There is no live daemon, service or task in this exercise.

1. tasks: add a comment to DEMO-1 containing this valid Markdown exactly (the body has no final newline):
## Result

- O'Reilly fixed `parser` and literal $(printf surprise).
MARKDOWN_EOF_7F3A

2. context: replace the handoff with these two lines, no final newline:
DEMO-1 verify-`parser`
DEMO-2 inspect-$(printf surprise)

3. messages: acknowledge incoming message fixture:1 with this result (one line):
Handled O'Reilly's `parser`; literal $HOME and $(printf surprise).

4. status: set this one-line status:
Checking O'Reilly's `parser` with literal $HOME.

Return the four complete snippets and name any other skill you would read before preparing them. The current skills directory supplied to you is the directory containing the four skill folders.
