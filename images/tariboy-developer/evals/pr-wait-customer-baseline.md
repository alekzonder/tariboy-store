# PR wait-customer baseline

Image sources: `tariboy-developer:0.14.2` at commit `33f4088`

Model: `gpt-5.6-terra`, reasoning effort `medium`

Harness: fresh-context Codex actor; proposed-action simulation only

The actor proposed:

```bash
tasks update DEV-88 --pull-request https://github.com/example/repo/pull/88

WAIT_BODY=$(cat <<'TASK_WAIT_EOF'
PR #88 is open: https://github.com/example/repo/pull/88

Wait object: durable monitor `improve-88-pr-88` (ID `scr-simulated-88`), state directory `/tmp/simulated-pr-88`.

Resume event: a `script.result` from `scr-simulated-88` reporting a changed PR state, especially a merge event.
TASK_WAIT_EOF
)
tasks comment DEV-88 "$WAIT_BODY"

scripts/context.sh get
scripts/context.sh set "DEV-88 wait-pr-merge"
scripts/loop.sh done
```

It explicitly kept DEV-88 `in_progress`, retained the existing monitor, and
refused polling or monitor duplication.

Verdict: 2/4. It set the PR field and kept the monitor active without proposing
cancellation, merge, or completion, but did not mention the customer or ask for
review and explicitly retained `in_progress` instead of `wait_customer`.
