---
{
  "id": "playbook-blocker-escalation",
  "title": "Task blocker escalation",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "task",
    "blocker",
    "blocking",
    "escalation",
    "sso"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Task blocker escalation

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Resolve the exact blocked task. Partial or duplicate titles require clarification.

## Evidence to collect
Follow blocker_task_id until no link, missing row, cycle or the bounded depth is reached. Show prerequisite status and owner; a completed prerequisite may be a stale recorded link.

## Proposed next action
Offer the blocker owner and recorded manager as possible contacts. A dependency does not establish personal blame or authority to reassign work.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
