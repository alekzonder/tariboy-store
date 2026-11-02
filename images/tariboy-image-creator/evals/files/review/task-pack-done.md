# Task pack DEV-41

Assess the whole task: write `task_key`, no `iteration_id`.

## Task
key: DEV-41
title: Fix the retry delay in the mail sender
status: done
assignee: agent:dev-a
created_at: 2026-11-01T08:00:00Z
workflow: none
description:
The mail sender retries at once after an error. Wait 5 seconds between retries. Deliver a pull request for review by user:owner.

comments (latest 8):
- comment 290 by agent:dev-a at 2026-11-01T09:00:00Z: @user:owner Plan: add a 5 s delay in mail/retry.go and a test. Approve?
- comment 291 by user:owner at 2026-11-01T12:00:00Z: Approved.
- comment 295 by user:owner at 2026-11-02T10:00:00Z: Changes requested: the delay must be configurable.
- comment 297 by user:owner at 2026-11-02T16:00:00Z: Changes requested: the config key name must be `mail.retry_delay`.
- comment 299 by agent:dev-a at 2026-11-02T17:00:00Z: @user:owner Which unit do you want for `mail.retry_delay`, seconds or a duration string?
- comment 300 by user:owner at 2026-11-02T18:00:00Z: A duration string.
- comment 302 by user:owner at 2026-11-03T09:00:00Z: Merged. Thanks.

events (sequence kind actor payload):
- 8801 task.created user:owner {"key": "DEV-41"}
- 8805 task.question_asked agent:dev-a {"to": "user:owner", "comment_id": 290}
- 8809 task.comment_added user:owner {"comment_id": 295, "review": "changes_requested"}
- 8812 task.comment_added user:owner {"comment_id": 297, "review": "changes_requested"}
- 8813 task.question_asked agent:dev-a {"to": "user:owner", "comment_id": 299}
- 8820 task.done agent:dev-a {}

## Measures
created_at: 2026-11-01T08:00:00Z  done_at: 2026-11-03T09:10:00Z
rework rounds (changes_requested or reopened): 2
questions to the customer (task.question_asked or waits): 2

## Iteration assessments of this task
- as-20261103T100000Z-000011 iteration dev-a-20261101085500-1: Plan asked and approved before the change. image_process 100, role 100, task_fit 100.
- as-20261103T100000Z-000012 iteration dev-a-20261102103000-1: Made the delay configurable after review. image_process 100, role 100, task_fit 90.
- as-20261103T100000Z-000013 iteration dev-a-20261102163000-1: Renamed the key after a second review; asked the unit. image_process 100, role 100, task_fit 85.
