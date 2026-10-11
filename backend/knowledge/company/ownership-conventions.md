---
{
  "id": "ownership-conventions",
  "title": "Responsibilities and ownership conventions",
  "category": "company",
  "status": "reference",
  "version": 1,
  "updated_at": "2026-10-11",
  "tags": [
    "owner",
    "responsibility",
    "blocker"
  ],
  "sources": [
    "schema:tasks.blocker_task_id",
    "schema:projects.owner_employee_id"
  ],
  "classification": "internal-reference",
  "author": "KAIROS implementation proposal"
}
---
# Responsibilities and ownership conventions

## Owner fields
Projects, tasks and issues use owner_employee_id. Meetings use organizer_employee_id. Contracts use contract_owner_id. Clients use account_manager_id. These foreign keys take precedence over legacy textual owner labels. The browser cannot choose the authenticated employee ID, role or department.

## Dependencies
tasks.blocker_task_id points to a recorded prerequisite task. It is evidence of a dependency, not evidence of fault. Resolve the blocking task and its owner separately, including the case where the prerequisite is already completed.

## Gaps
No recorded owner means unknown ownership. Do not substitute a department head, meeting attendee, communication author or similarly named person. Proposed handoffs must identify an intended target and await a separately authorized write workflow.
