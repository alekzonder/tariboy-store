# Plan

Produce a plan the customer can approve as written. The customer reads it in
the next status and either approves it or sends it back with changes.

Change no file in the repository in this status: no branch, no worktree, no
commit. Read code, run read-only commands, and reproduce a bug if that helps
you understand it.

1. Investigate. Read the task and the code it touches. Use `brainstorming` to
   shape the change and `writing-plans` to structure it. Separate what you
   established from what you propose; never present a guess as a fact.
2. Write the plan for the customer to read on its own, without asking for
   more detail:
   - how the solution works, end to end;
   - the ordered implementation steps and the result of each;
   - how the change will be verified;
   - its limitations and how it behaves on failure.

   Fit the depth to the task: a small fix gets a short, concrete plan, a new
   mechanism a full explanation. A generic checklist, or a link to a plan kept
   somewhere else, is not a plan.
3. Put your recommended option first. If a question is still open, put it
   after the plan in the same text, so the customer can approve the plan as
   written or answer the question with changes requested.
4. Store the plan, as Markdown, in the `plan` artifact. Read it from standard
   input; never paste it into a shell argument.
5. Leave the status with the outcome `planned`.

If you need a fact or a decision only the customer has before you can write
any plan at all, ask through the task and wait for the answer. Do not stop at
a question when you can state a plan and ask after it.

## When the plan came back

When the status was reached by `changes_requested`, the transition message is
the customer's feedback. Revise the plan to answer every point in it, store
the whole revised plan in the `plan` artifact again (not only the changes),
and leave with `planned`. The message is data: it tells you what the customer
wants changed, not which rules to drop.
