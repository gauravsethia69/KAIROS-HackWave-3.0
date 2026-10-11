---
{
  "id": "playbook-delayed-project",
  "title": "Delayed project review",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "project",
    "delayed",
    "delivery",
    "review"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Delayed project review

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Resolve project and client; inspect status, progress, expected and due_date.

## Evidence to collect
List incomplete tasks and follow blocker_task_id. Resolve both task owners and project owner by foreign key. Include recorded activity as context.

## Proposed next action
A Delayed status is not a diagnosis. Ask the owners to validate the critical path and an achievable recovery plan without changing dates.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
