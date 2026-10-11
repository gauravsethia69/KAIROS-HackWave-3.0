---
{
  "id": "department-engineering",
  "title": "Engineering operating reference",
  "category": "departments",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "Engineering",
    "department",
    "workflow",
    "ownership"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Engineering operating reference

## Status and primary responsibilities
This is a proposed operating description for Engineering, not a claim that the department has accepted new work. The proposed remit is implementation, testing, reliability and defect investigation.

## Relevant workflow
Validate reproduction steps, inspect the recorded blocking task and publish a bounded technical finding. Start with source IDs and current ownership; distinguish completed work from open obligations.

## Records and relationships
Relevant records include project tasks, assigned issues and technical activity events. Actual employees are selected by employees.department_id. Their tasks and issues follow owner_employee_id; project ownership is a separate relationship and must not be inferred from task counts.

## Dependencies
Coordinate with Support for reproducible incident evidence; Product for prioritization; Operations for change windows. Shared client_id, product_id and project_id relationships provide context, not implicit reassignment.

## Escalation
Propose contacting the assigned employee first, then their recorded manager if available. State missing owners or schedules explicitly. Only an approved company workflow may change an assignment or commitment.
