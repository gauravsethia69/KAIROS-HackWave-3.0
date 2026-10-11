---
{
  "id": "organization-reporting",
  "title": "Organization and reporting model",
  "category": "company",
  "status": "reference",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "organization",
    "manager",
    "department"
  ],
  "sources": [
    "schema:employees.manager_id",
    "schema:employees.department_id"
  ],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Organization and reporting model

## Established relationships
employees.department_id references departments.id. employees.manager_id references employees.id. The seven named departments supplied for this project are Engineering, Customer Success, Product, Sales, Support, Operations and Data & Analytics. Look up actual membership rather than inferring it from a job title.

## Manager interpretation
A manager link identifies a recorded reporting relationship. It does not prove incident authority, approval rights or current availability. A missing manager is reported as missing. Cycles and absent records terminate traversal instead of manufacturing a hierarchy.

## Proposed routing
Start a delivery question with the recorded work owner. If escalation is needed, offer the recorded manager as a possible contact, explicitly as a proposed action. Do not claim that the manager caused or can resolve a blocker.
