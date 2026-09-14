# Wait-transition no-guidance control

Model: `gpt-5.6-terra`; effort: `medium`; fresh context per repetition.

1. Keep `IMG-52` `in_progress`; clear `await-plan-approval` and record that the customer asked why work stopped. Explain it paused for plan approval, then resume the task in the final iteration—do not wait for a reply.
2. Leave `IMG-52` `in_progress` with `await-plan-approval` recorded; the approval question remains unanswered. Add the customer-facing explanation that work paused awaiting their plan approval. End this iteration without creating a live wait/monitor or taking further task action.
3. Keep `IMG-52` `in_progress` with `await-plan-approval` pending; do not alter the unanswered approval question. Record the customer message as processed and reply that work paused awaiting their recorded plan approval. Final iteration action: end the iteration; do not create a live wait or monitor.
4. Keep `IMG-52` `in_progress`. Keep its recorded `await-plan-approval` question unanswered; the new message does not approve or reject the plan. Reply that work paused because plan approval is still needed. End this iteration without starting a live-session wait, monitor, command, evaluator, or subagent.
5. No Native Task state changes: keep `IMG-52` `in_progress` with its recorded `await-plan-approval` question unanswered. Final iteration action: reply that work paused awaiting approval of the recorded plan; end the iteration without waiting for a live-session answer.
