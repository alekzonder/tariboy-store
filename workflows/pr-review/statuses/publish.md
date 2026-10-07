# Publish

The customer approved the review. Publish it on the pull request exactly as
approved: the `review_comments` artifact, on the commit in `head_sha`.

1. Publish with the `pull-request-review` skill's `publish`. It creates one
   review with the event `COMMENT`: never approve, request changes, merge,
   close or push. Running it again finds the review it already published
   instead of creating a second one.
2. Store the review URL it prints in `published_review` as the VALUE argument,
   `ttasks artifacts set KEY published_review URL`.
3. Leave the status with the outcome `published`. A check confirms the review
   exists on the pull request, on the reviewed commit, with every inline
   comment. If it rejects, fix what it names and advance again.

Change no text of the approved review. If GitHub refuses it, or the token
cannot write reviews, ask the customer through the task and wait for the
answer; do not edit the review to make it pass.
