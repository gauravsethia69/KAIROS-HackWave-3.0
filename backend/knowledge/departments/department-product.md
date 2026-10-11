---
{
  "id": "department-product",
  "title": "Product operating reference",
  "category": "departments",
  "status": "proposed",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "Product",
    "department",
    "workflow",
    "ownership"
  ],
  "sources": [],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Product operating reference

## Status and primary responsibilities
This is a proposed operating description for Product, not a claim that the department has accepted new work. The proposed remit is product intent, acceptance criteria and prioritization.

## Relevant workflow
Separate a product decision from a delivery blocker and record the evidence needed before reprioritization. Start with source IDs and current ownership; distinguish completed work from open obligations.

## Records and relationships
Relevant records include product-linked projects, tasks and product feedback. Actual employees are selected by employees.department_id. Their tasks and issues follow owner_employee_id; project ownership is a separate relationship and must not be inferred from task counts.

## Dependencies
Coordinate with Engineering for effort and feasibility; Customer Success for client context; Data & Analytics for measurement. Shared client_id, product_id and project_id relationships provide context, not implicit reassignment.

## Escalation
Propose contacting the assigned employee first, then their recorded manager if available. State missing owners or schedules explicitly. Only an approved company workflow may change an assignment or commitment.
