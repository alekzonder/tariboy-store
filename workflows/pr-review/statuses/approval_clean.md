# Confirm a clean review

The reviewer found no problems in the pull request. Read the review in the
`review` artifact:

```bash
ttasks artifacts show KEY review
```

Choose one outcome:

- `close`: the task ends; nothing is published on the pull request.
- `revise`: the review goes back to the reviewer. Say what to check again in
  the message of this outcome; the reviewer works from that message.

```bash
ttasks advance KEY --outcome close --from approval_clean
ttasks advance KEY --outcome revise --from approval_clean --message 'TEXT'
```
