```bash
BODY=$(cat <<'TASK_COMMENT_EOF'
## Result

- O'Reilly fixed `parser` and literal $(printf surprise).
MARKDOWN_EOF_7F3A
TASK_COMMENT_EOF
)
/home/agent/.tariboy/agents/tariboy-image-creator/workdir/improve-84/skills/tasks/scripts/tasks.sh comment DEMO-1 "$BODY"
```

```bash
HANDOFF=$(cat <<'CONTEXT_EOF'
DEMO-1 verify-`parser`
DEMO-2 inspect-$(printf surprise)
CONTEXT_EOF
)
/home/agent/.tariboy/agents/tariboy-image-creator/workdir/improve-84/skills/context/scripts/context.sh set "$HANDOFF"
```

```bash
RESULT=$(cat <<'MESSAGE_RESULT_EOF'
Handled O'Reilly's `parser`; literal $HOME and $(printf surprise).
MESSAGE_RESULT_EOF
)
/home/agent/.tariboy/agents/tariboy-image-creator/workdir/improve-84/skills/messages/scripts/messages.sh message processed fixture:1 "$RESULT"
```

```bash
STATUS=$(cat <<'STATUS_EOF'
Checking O'Reilly's `parser` with literal $HOME.
STATUS_EOF
)
/home/agent/.tariboy/agents/tariboy-image-creator/workdir/improve-84/skills/status/scripts/status.sh set "$STATUS"
```

Other skill to read: none.
