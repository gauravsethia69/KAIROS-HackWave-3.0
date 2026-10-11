---
{
  "id": "playbook-ownership-handoff",
  "title": "Cross-department ownership handoff",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "handoff",
    "ownership",
    "collaboration",
    "department"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Cross-department ownership handoff

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Identify the current owner using the entity-specific employee foreign key.

## Evidence to collect
Attach source IDs, current status, recorded dependencies, receiving team context and unresolved questions. Use communications only as evidence of recorded messages.

## Proposed next action
Ask the proposed receiving owner to acknowledge. This read-only system neither approves nor writes a handoff; the existing owner remains authoritative until an approved record changes.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
