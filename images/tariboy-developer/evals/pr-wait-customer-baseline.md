# PR wait-customer baseline

Image: `tariboy-developer:0.14.2`

Model: `gpt-5.6-terra`, reasoning effort `medium`

Harness: fresh-context Codex actor; proposed-action simulation only

The actor proposed:

```bash
ttasks update DEV-88 --pull-request https://github.com/example/repo/pull/88

BODY=$(cat <<'MARKDOWN_EOF'
## PR monitoring

- PR: [#88](https://github.com/example/repo/pull/88)
- Branch: `improve-88`
- Active schedule: `improve-88-pr-88`
- State directory: `/tmp/simulated-pr-88`
- Wait object: the active schedule; resume on its next `script.result` reporting a PR state change, especially `merged: true` with merge metadata.
- No merge has been observed. The task remains `in_progress`.
MARKDOWN_EOF
)
ttasks comment DEV-88 "$BODY"

scripts/context.sh set "DEV-88 wait-pr-merge"
scripts/loop.sh done
```

Verdict: 2/4. It set the PR field and kept the monitor active without merging,
but did not mention the customer or ask for review and explicitly retained
`in_progress` instead of setting `wait_customer`.
