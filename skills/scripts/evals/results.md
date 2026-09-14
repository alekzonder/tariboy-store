# External prerequisite failure evaluation

- Case: `4`
- Date: `2026-09-14`
- Harness: fresh-context Codex subagents, simulated actions only
- Model: `gpt-5.6-terra`
- Reasoning effort: `medium`
- Baseline skill SHA-256: `b112e460026f2c437db8cc71a12e6e93385bf9ef0a38b8f94e59341bd2948686`
- Candidate skill SHA-256: `5fa37145cf493c39341875d096936ff888b29e834a2a1f34783f563c988c10f7`
- Scenario SHA-256 after case addition: `0e5d0dde9a7bc98352a2464bc8aa1eeca7bea21e7d2dd3b4a3d3dd3f87489f16`

All runs were simulations. No task, schedule, PR, credential, or repository state was exposed to the actors or mutated by them.

## Baseline: 0/5 pass

1. Proposed disabling the schedule and one customer message, but supplied no `cancel`, `rm`, task-state, or loop command.
2. Proposed disabling the schedule and retaining the customer wait, but supplied no lifecycle or loop commands.
3. Proposed both required schedule commands, but omitted the explicit customer-answer and loop lifecycle.
4. Proposed disabling the schedule and one customer message, but supplied no `cancel`, `rm`, task-state, or loop command.
5. Proposed the nonexistent command `codex schedules disable`; omitted removal and loop completion.

Representative verbatim baseline trace:

```text
codex schedules disable scr-tariboy-developer-jack-20260914102103-000000001
Stopped the recurring PR monitor after repeated identical GH_TOKEN failures.
```

## Candidate wording iterations

Two unscored path-based probes inherited the main checkout and therefore did not prove which skill bytes were used. They were excluded. Three embedded-source runs then exposed one remaining omission: all used `cancel` plus `rm`, but two omitted explicit loop completion. The candidate added the exact `scripts/loop.sh done` action before the final matched run.

## Candidate: 5/5 pass

Every final run:

- used `scripts/scripts.sh cancel` and `scripts/scripts.sh rm` with the schedule ID;
- reused question 514 and kept `wait_customer` without another repeated failure comment;
- treated the customer answer as the only resume event;
- ended with `scripts/loop.sh done`;
- did not retry, replace the schedule, or run `make full-check`.

Representative verbatim candidate trace:

```text
scripts/scripts.sh cancel scr-tariboy-developer-jack-20260914102103-000000001
scripts/scripts.sh rm scr-tariboy-developer-jack-20260914102103-000000001

Native Task IMPROVE-101: retain wait_customer; reuse unanswered customer question 514 as the only resume event. No new communication.

scripts/loop.sh done
```

## Limitations

The harness evaluated proposed behavior, not a live daemon integration. Customer mention syntax and exact task CLI flags remain owned by the `tasks` and `cli-text` skills.
