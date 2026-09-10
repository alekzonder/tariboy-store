# Case A control responses

## Repetition 1

Title: `DEV-42: Реализация задачи`

Body:

```markdown
## Описание

Изменения для задачи DEV-42.

## Проверка

Полная проверка ветки выполнена перед отправкой.
```

Ensure command:

```bash
"$UTILITY" ensure --repo "$REPO" --head "$HEAD" --base "$BASE" \
  --title "DEV-42: Реализация задачи" \
  --body $'## Описание\n\nИзменения для задачи DEV-42.\n\n## Проверка\n\nПолная проверка ветки выполнена перед отправкой.'
```

## Repetition 2

Title: `DEV-42: Реализовать изменения по задаче`

Body: `Реализованы изменения, предусмотренные задачей DEV-42.`

Ensure command:

```bash
"$UTILITY" ensure --repo "$REPO" --head "$HEAD" --base "$BASE" --title "DEV-42: Реализовать изменения по задаче" --body "Реализованы изменения, предусмотренные задачей DEV-42."
```

## Repetition 3

Title: `DEV-42: Выполнение задачи`

Body: `Выполняет требования задачи DEV-42.`

Ensure command:

```bash
"$UTILITY" ensure --repo "$REPO" --head "$HEAD" --base "$BASE" --title "DEV-42: Выполнение задачи" --body "Выполняет требования задачи DEV-42."
```

## Repetition 4

Title: `DEV-42: Выполнить задачу`

Body: `Выполнены изменения по задаче DEV-42.`

Ensure command:

```bash
"$UTILITY" ensure --repo "$REPO" --head "$HEAD" --base "$BASE" \
  --title "DEV-42: Выполнить задачу" \
  --body "Выполнены изменения по задаче DEV-42."
```

## Repetition 5

Title: `DEV-42: Выполнение задачи`

Body: `Выполняет задачу DEV-42.`

Ensure command:

```bash
"$UTILITY" ensure --repo "$REPO" --head "$HEAD" --base "$BASE" --title "DEV-42: Выполнение задачи" --body "Выполняет задачу DEV-42."
```

All five controls used `ensure`, wrote Russian title/body text and included
`DEV-42`. Full-pass verdict: 0/5.
