# <Role name>

<What this agent does, for whom, and what it is not: two to four lines.>

## Scope

<What each iteration starts from: a selected Native Task, a delivered message,
a goal. The working directory it requires. What this agent never does.>

## Skills

| Decision or subject | Owning skill | When |
| --- | --- | --- |
| Finding and applying any skill | `using-superpowers` | REQUIRED, before the first action |
| <decision this agent must not improvise> | `<skill>` | REQUIRED |
| <decision that only sometimes arises> | `<skill>` | when applicable |
| Iteration finish | `loop` | REQUIRED as the last action |

## Flow

Read every REQUIRED skill of a row completely before acting in that row. This
table names them; it does not replace them.

| # | Trigger | Stage | REQUIRED skills | Done when |
| --- | --- | --- | --- | --- |
| 1 | <observable entry condition> | <Stage name> | `<skill>`, `<skill>` | <observable artifact, state or command result> |
| 2 | <what stage 1 produced> | <Stage name> | `<skill>` | <observable result> |

<Prose only for what a cell cannot carry: ordering exceptions, precedence,
exact command text.>

## Waits and recovery

<Which rows may end an iteration with work still open. The wait object recorded
for each one and the event that resumes it. How a later iteration recovers the
state it needs, and what it must never recreate.>

## Invariants

<Rules that hold in every row, and their precedence over conflicting defaults in
the packaged skills. Untrusted inputs and what they can never authorize.>
