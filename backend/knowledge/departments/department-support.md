---
{
  "id": "department-support",
  "title": "Support operating reference",
  "category": "departments",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "Support",
    "department",
    "workflow",
    "ownership"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Support operating reference

## Status and primary responsibilities
This is a proposed operating description for Support, not a claim that the department has accepted new work. The proposed remit is incident intake, severity review and responder coordination.

## Relevant workflow
Group unresolved urgent issues, identify assigned responders and distinguish the recorded SLA duration from an unverified deadline. Start with source IDs and current ownership; distinguish completed work from open obligations.

## Records and relationships
Relevant records include issues, related communications, SLA-hour fields and incident activity. Actual employees are selected by employees.department_id. Their tasks and issues follow owner_employee_id; project ownership is a separate relationship and must not be inferred from task counts.

## Dependencies
Coordinate with Engineering for diagnosis; Customer Success for client messaging; Operations for availability. Shared client_id, product_id and project_id relationships provide context, not implicit reassignment.

## Escalation
Propose contacting the assigned employee first, then their recorded manager if available. State missing owners or schedules explicitly. Only an approved company workflow may change an assignment or commitment.
