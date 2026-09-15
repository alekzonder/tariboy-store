# Customer-answer wait candidate, first wording

Image `0.14.4`, model `gpt-5.6-terra`, effort `medium`, fresh context per repetition.

## Repetitions 1 and 3

Read `DEV-52` once, mention `@user:alex`, set `wait_customer`, preserve `DEV-52 wait-answer`, handle the already-processed message, and end with `scripts/loop.sh done`.

## Repetitions 2, 4, and 5

Mention `@user:alex`, set `wait_customer`, preserve `DEV-52 wait-answer`, handle the already-processed message, and end with `scripts/loop.sh done`; omit the authoritative task read.

Full passes: `2/5`.
