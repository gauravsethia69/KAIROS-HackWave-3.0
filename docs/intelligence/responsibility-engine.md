# Recorded responsibility

`backend/services/responsibility.py` resolves an `EntityRef` against a bounded, read-only snapshot using verified foreign keys. It never infers owners from the older textual `owner` fields.

| Entity | Recorded owner relationship |
| --- | --- |
| Project/task/issue | `owner_employee_id` |
| Meeting | `organizer_employee_id` |
| Contract | `contract_owner_id` |
| Client | `account_manager_id` |
| Employee | The employee record itself |

The response includes `entity`, safe `record`, optional `owner`, `department`, `manager`, `related`, `blocker_chain`, `proposed_contacts`, `evidence` and `limitations`. Employee relationships include assigned tasks, owned projects/issues, organized or attended meetings and schedule blocks. Employee name search accepts exact IDs and normalized partial names. Intent matching additionally supports conservative fuzzy names.

Task dependencies follow `blocker_task_id` up to eight links, with cycle and missing-record detection. Each link includes the recorded blocking task, owner, manager and project. A dependency is not proof of delay, personal fault or escalation authority. A missing owner/manager remains missing; it is never replaced by a guessed colleague. Proposed contacts are labeled as such.

Related collections are bounded to 100 records and recent activity to 20. The snapshot itself is bounded; limitations accompany truncated collections. Only records visible under the existing authenticated PostgreSQL role are available. New department/role access policies are not invented.

`GET /api/intelligence/employees/me` derives the employee ID from `current_user`. Browser query parameters cannot override it. Looking up another visible employee through the entity endpoint is a record lookup, not impersonation; existing database policies determine visibility.

Fixture example: task `t1` (Validate SSO callback fix) records blocker `t2`. Tests verify both owners through employee IDs, department `eng`, recorded manager and missing-owner behavior. These are isolated test IDs, not asserted production identities.
