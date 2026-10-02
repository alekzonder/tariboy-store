# Complete

The pull request merged. Its merge commit is in the `merge_commit` artifact.
Bring the local repository up to date, remove the task's workspace, and record
the result.

1. In the repository's main checkout, fetch and fast-forward the local base
   branch so it contains the merge commit. Never reset, rebase, or force it.
   If the fast-forward fails because the local branch diverged, keep it
   exactly as it is, post the failure on the task, and ask the customer
   through the task.
2. Remove the task's worktree and then its local branch.
3. Set your working directory to the repository's main checkout with the
   `workdir` skill. The check that ends this status runs in your working
   directory: it looks there for the merge commit on the base branch and for
   a leftover worktree or branch.
4. Record one consolidated comment on the task with:
   - `Required:` what the task asked for;
   - `Completed:` what was delivered, with the pull request URL;
   - `Verification:` the verification that ran on the final commit, and the
     result of the pull request's required checks on its last head;
   - `Integration:` the merge commit and that the base branch contains it;
   - `Cleanup:` the worktree and branch you removed.
5. Leave the status with the outcome `cleaned`. If the check rejects, do what
   its message names and advance again.

Do not rerun the branch's suite on the base branch only because the pull
request merged; the pull request's checks already ran on its final commit.
