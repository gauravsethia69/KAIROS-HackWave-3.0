---
{
  "id": "department-operations",
  "title": "Operations operating reference",
  "category": "departments",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "Operations",
    "department",
    "workflow",
    "ownership"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Operations operating reference

## Status and primary responsibilities
This is a proposed operating description for Operations, not a claim that the department has accepted new work. The proposed remit is delivery coordination, dependencies and scheduling.

## Relevant workflow
Compare actual versus expected progress and trace recorded blockers before proposing revised work sequencing. Start with source IDs and current ownership; distinguish completed work from open obligations.

## Records and relationships
Relevant records include owned projects, tasks, schedule blocks and meeting logistics. Actual employees are selected by employees.department_id. Their tasks and issues follow owner_employee_id; project ownership is a separate relationship and must not be inferred from task counts.

## Dependencies
Coordinate with Engineering for prerequisites; Customer Success for client scheduling; department managers for capacity decisions. Shared client_id, product_id and project_id relationships provide context, not implicit reassignment.

## Escalation
Propose contacting the assigned employee first, then their recorded manager if available. State missing owners or schedules explicitly. Only an approved company workflow may change an assignment or commitment.
