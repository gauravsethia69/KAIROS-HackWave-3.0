---
{
  "id": "playbook-usage-decline",
  "title": "Product usage decline investigation",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "usage",
    "adoption",
    "decline",
    "investigation"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Product usage decline investigation

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Resolve the client-product pair and an explicit date window. Compare equal-length adjacent periods.

## Evidence to collect
Use product_usage for measured daily activity and sessions. Check issue timestamps and communications. Flag missing days and do not equate summed daily counts with unique users.

## Proposed next action
Separate observed change from possible factors. Propose cohort or instrumentation checks; never assign an incident as the cause solely because dates overlap.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
