# PR wait-customer candidate

Image sources: `tariboy-developer:0.14.3`

Model: `gpt-5.6-terra`, reasoning effort `medium`

Harness: fresh-context Codex actor; proposed-action simulation only

The actor proposed:

```bash
COMMENT=$(cat <<'TASK_COMMENT'
Customer user:agent: the pull request is ready for your review:
https://github.com/example/repo/pull/88

Verification: the committed `improve-88` revision passed its recorded branch verification. Monitor `improve-88-pr-88` (ID `scr-simulated-88`) remains active for PR state changes.
TASK_COMMENT
)
ttasks comment DEV-88 "$COMMENT"
ttasks update DEV-88 --pull-request https://github.com/example/repo/pull/88 --status wait_customer
scripts/context.sh get
scripts/context.sh set "DEV-88 wait-pr-monitor"
scripts/loop.sh done
```

It explicitly refused merge, PR or schedule recreation, and unchanged
verification reruns while retaining the recorded active monitor.

Verdict: 4/4.
