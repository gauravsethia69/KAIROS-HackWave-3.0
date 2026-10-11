---
{
  "id": "playbook-support-triage",
  "title": "Support incident triage",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "support",
    "incident",
    "urgent",
    "severity",
    "sla"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Support incident triage

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Find unresolved High or Critical severity issues and identify their client, product and owner.

## Evidence to collect
Read detail, sla_hours, related communications and activity. SLA hours are a recorded duration; a date without a precise start timestamp is insufficient for an exact breach claim.

## Proposed next action
Propose contacting the assigned responder and their recorded manager if escalation is warranted. Do not invent on-call rotations or declare root cause.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
