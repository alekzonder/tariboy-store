# Deliver

This workflow takes one improvement of an image, workflow or skill from a reviewer finding to a
published image. In this status you hand the verified change to the customer as one pull request.
The customer merges it, or the merge watch does when the queue sets `AUTO_MERGE`; you never do.

1. Check that the branch is pushed and its head commit is the one the `verification` artifact names.
   Run `git rev-parse HEAD` in the worktree and compare it with the 40-character SHA in the
   `verification` artifact. If they differ, go back: run `make check` on the new head, store a new
   `verification` artifact with the new SHA, store again the `evals` results that the new commits
   touched, push, and compare again. Continue only when the two SHAs are equal. Run the same
   comparison again just before `submitted`.
2. Find or create the task's one pull request with `github-pr-workflow`'s `ensure` (find the one in
   `pull_request` first); never open a second one. The base is the repository's default branch.
   Title and body are English and carry no task key. The body has what changed, the versions bumped
   (old and new), the base and new eval table from the `evals` artifact with the model and cost,
   and the verification.
3. Store the pull request's URL in the `pull_request` artifact, exactly as
   `https://github.com/OWNER/REPO/pull/NUMBER`. Pass it as the VALUE argument,
   `ttasks artifacts set KEY pull_request URL`: standard input keeps a trailing newline, which the
   check rejects.
4. Post one task comment that mentions the customer with the pull request link, the verification and
   the eval table. Do it before `submitted`: after it a script owns `merge` and your task writes fail.
5. Leave the status with the outcome `submitted`. A check confirms the pull request is open from
   `branch` at the verified commit, targets the default branch and names no task key. If it
   rejects, fix what it names and advance again.

After `submitted`, the daemon watches the pull request. Do not schedule a monitor. Never merge or
close the pull request.
