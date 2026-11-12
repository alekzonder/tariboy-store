# Publish

This workflow takes one improvement of an image, workflow or skill from a reviewer finding to a
published image. The pull request is merged. In this status you publish the merged images
and record the result, so the improvement reaches the agents.

The merge commit is in the `merge_commit` artifact.

Open the skills this status names with the Skill tool before the first command, file read or edit,
`ttasks show` and `git status` included: `tariboy-image-delivery`, `image-creator` and `cli-text`. A command run before these reads is a
violation, and later reads do not undo it.

1. Fetch and fast-forward the base branch in the main checkout until it contains the merge commit.
   Never reset, rebase or force it. If the fast-forward fails because the local branch diverged,
   keep it as it is and ask the customer through the task. Prove it:
   `git merge-base --is-ancestor MERGE_COMMIT BASE` exits 0.
2. Run the post-merge checks (`make check`) on the base.
3. Select the affected images by the merge's changed paths, the local skills their
   `skills-lock.json` records, and the `extends` chains, as `tariboy-image-delivery` says in
   "Publication after merge". Build each one from a disposable copy under the workdir, under its
   `image_version` tag and under `latest`, with the `image-creator` launcher. Both builds of one
   image must report the same digest. A path under `workflows/` selects no image: never build a
   workflow.

   A selected image whose `image_version` the merge did not bump is a blocker. Build and publish no
   tag of it, `latest` included. Bump and commit nothing after the merge. Ask the customer through
   the task, with `ttasks ask`, for a follow-up change, and wait.
4. Remove the task's worktree and local branch. Use `git branch -D` once step 1 proved the merge
   commit is on the base.
5. Store the result in the `publication` artifact, as JSON, from standard input:

   ```json
   {"images": [{"name": "NAME", "version": "X.Y.Z", "version_digest": "64 hex", "latest_digest": "64 hex"}],
    "workflows": [{"name": "NAME", "workflow_version": "X.Y.Z"}]}
   ```

   Use the full digests. List each merged workflow with its merged version; the operator builds it
   with `tariboy workflow build STORE/NAME` and binds a queue with
   `ttasks queue workflow set QUEUE NAME:VERSION`.
6. Post one consolidated task comment with `Required:`, `Completed:`, `Verification:`,
   `Integration:` (pull request URL and merge commit), `Publication:` (per image: name, version,
   `latest`, digest; per workflow: version, not built by you, and the two operator commands) and
   `Cleanup:`. Mention the customer.
7. Leave the status with the outcome `published`. A check confirms each image has its version and
   `latest` under one full digest. If it rejects, fix the build or the record and advance again.
   Never record a digest you did not read from the build output.
