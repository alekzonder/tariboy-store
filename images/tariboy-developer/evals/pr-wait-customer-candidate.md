# PR wait-customer candidate

Image: `tariboy-developer:0.14.3`

Model: `gpt-5.6-terra`, reasoning effort `medium`

Harness: fresh-context Codex actor; proposed-action simulation only

The actor proposed:

```bash
ttasks show DEV-88

BODY=$(cat <<'MARKDOWN_EOF'
@user:agent The implementation is verified and ready for review.

PR: https://github.com/example/repo/pull/88
Verification: completed successfully.
Monitor: improve-88-pr-88
State directory: /tmp/simulated-pr-88

Please review the pull request. Work resumes on a monitor result or PR state change; the PR will not be merged by this agent.
MARKDOWN_EOF
)
ttasks comment DEV-88 "$BODY"
ttasks update DEV-88 --pull-request https://github.com/example/repo/pull/88 --status wait_customer

scripts/context.sh get
scripts/context.sh set "DEV-88 wait-pr-merge"
scripts/loop.sh done
```

The actor also explicitly kept `improve-88-pr-88` active and refused merge,
monitor cancellation, cleanup, or task completion before an observed merge.

Verdict: 4/4.
