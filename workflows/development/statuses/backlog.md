# Backlog

A new task waits here until you start it. No agent takes a task in this
status, and no work begins on it.

Before you start the task, make its title and description say what you want:
the developer plans from them in the next status and does not ask for more
detail before writing the plan.

Choose the one outcome:

- `start`: the task moves to `plan`, where a developer from the pool takes it
  and writes a plan for your approval. Add anything the developer should know
  in the message of this outcome.

```bash
ttasks advance KEY --outcome start --from backlog --message 'TEXT'
```

Leave a task here for as long as it should not be worked on.
