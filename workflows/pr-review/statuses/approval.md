# Approve the review

The reviewer found problems in the pull request. Read the review in the
`review` artifact, and the exact text that would be published on GitHub in
`review_comments`:

```bash
ttasks artifacts show KEY review
ttasks artifacts show KEY review_comments
```

Choose one outcome:

- `publish`: the reviewer publishes `review_comments` on the pull request as
  one review comment, without approving or requesting changes.
- `revise`: the review goes back to the reviewer. Say what to change in the
  message of this outcome; the reviewer works from that message.
- `close`: the task ends and nothing is published, even though there are
  findings.

```bash
ttasks advance KEY --outcome publish --from approval
ttasks advance KEY --outcome revise --from approval --message 'TEXT'
ttasks advance KEY --outcome close --from approval
```
