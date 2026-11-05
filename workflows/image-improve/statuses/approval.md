# Approve the plan

The image creator found a finding that needs your approval before any change. The plan is in the
`plan` artifact: how the change works, the steps, how it will be verified and its limits. The
`triage` artifact says why the rule for changes without approval does not cover it.

Choose one outcome:

- `approved`: the image creator makes the change as written, with evals, and opens one pull
  request. The task then waits for you to merge it. The image creator never merges.
- `changes_requested`: the plan goes back to triage. Say what to change, and answer any open
  question, in the message of this outcome.
- `rejected`: the task closes and nobody works on it. Say why in the message.

Approve only the plan you read. If the scope changes later, request changes so that a new plan is
written.
