# Research

The outcome of this status is a report that answers the question in the
task. Read the task first and state the question to yourself in one sentence;
every part of the report serves that answer.

How you do the work is your choice: read, search, run experiments, compare
sources. Pick what the question needs. Keep track of where each claim comes
from, and say plainly what you could not establish.

If the question is unclear, or you need a decision or a fact only the customer
has, ask through the task and wait for the answer. Do not guess at the
question and research the guess.

When the report is ready:

1. Store it as the `report` artifact, reading the Markdown from standard input:

   ```sh
   ttasks artifacts set KEY report <<'EOF'
   # Title

   The answer first, then the evidence.
   EOF
   ```

2. Leave the status:

   ```sh
   ttasks advance KEY --outcome reported
   ```

Replace `KEY` with the task key. Put the answer at the top, then the evidence,
then open questions and the limits of what you found.

A report that does not answer the question is not finished. Do not advance
until it does.
