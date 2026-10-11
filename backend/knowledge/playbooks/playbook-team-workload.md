---
{
  "id": "playbook-team-workload",
  "title": "Team workload analysis",
  "category": "playbooks",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "workload",
    "capacity",
    "schedule",
    "team",
    "department"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Team workload analysis

## Procedure status
Proposed; awaiting company approval. This procedure changes no database assignments or deadlines.

## Scope
Resolve department from an explicit entity or derive my team from the authenticated employee record.

## Evidence to collect
Group open tasks by owner_employee_id. Show estimated_hours and weekly_capacity_hours separately. Clip schedule blocks to the requested period and deduplicate overlapping occupied intervals.

## Proposed next action
Unscheduled time is not promised availability. Missing estimates and schedule coverage make capacity partial. Any staffing or reassignment is a proposal.

## Stop conditions
Ask for clarification on competing entity matches. Report missing/unauthorized records without guessing. On dependency outage return an explicit service error rather than a fabricated successful result.
