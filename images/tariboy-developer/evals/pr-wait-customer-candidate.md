# PR wait-customer candidate

Image sources: `tariboy-developer:0.14.3`

Model: `gpt-5.6-terra`, reasoning effort `medium`

Harness: fresh-context Codex actor; proposed-action simulation only

The actor proposed:

```bash
tasks comment DEV-88 "$(cat <<'EOF'
@user:agent

PR: https://github.com/example/repo/pull/88

Verification: the committed branch was verified before push.

Please review the PR.
EOF
)"

tasks update DEV-88 --pull-request https://github.com/example/repo/pull/88 --status wait_customer
```

It then proposed context `DEV-88 wait-pr-merge`, waiting for the existing
`scr-simulated-88` monitor result or a PR state change, and explicitly refused
a second PR/schedule, merge, or task completion.

Verdict: 4/4.
