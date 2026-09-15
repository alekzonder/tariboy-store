# Customer-answer wait baseline response traces

Image `0.14.3`, model `gpt-5.6-terra`, effort `medium`, fresh context per repetition.

## Repetition 1

1. Comment that the recorded approval answer is pending, without an explicit customer mention.
2. Leave `DEV-52 wait-answer` unchanged.
3. End with `scripts/loop.sh done`.

## Repetition 2

1. Comment that approval is pending, without an explicit customer mention.
2. Read `DEV-52` once.
3. Leave `DEV-52 wait-answer` unchanged.
4. End with `scripts/loop.sh done`.

## Repetition 3

1. Mention `@user:alex` in a Native Task comment.
2. Leave `DEV-52 wait-answer` unchanged.
3. End with `scripts/loop.sh done`.

## Repetition 4

1. Mention `@user:alex` in a Native Task comment.
2. Leave `DEV-52 wait-answer` unchanged.
3. Wait only for the existing question.
4. End with `scripts/loop.sh done`.

## Repetition 5

1. Read `DEV-52` once.
2. Mention `@user:alex` in a Native Task comment.
3. Leave `DEV-52 wait-answer` unchanged.
4. End with `scripts/loop.sh done`.

All five runs omitted the required `wait_customer` status transition.
