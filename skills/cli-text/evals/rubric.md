# Evaluator only

- JavaScript parses with the supplied body and tools object, without unsupported globals.
- Bash receives one exact argument after `set`, including empty text and two trailing newlines.
- Backticks, dollar substitutions, apostrophes, Unicode and backslashes remain literal; no extra commands execute.
- A complete-line heredoc delimiter collision is avoided; no invented CLI input flags.
- Performs `note-cli get` after a successful write; no unconditional success claim.

Run generated code only in a disposable subprocess with a recording stub CLI and a minimal environment. Never expose live credentials or tools. Record snippets, execution output, model/effort and fixture/source hashes. Repeat baseline/candidate five times with fresh actors; do not show this rubric to actors. Temperature/seed are unavailable through collaboration tools.
