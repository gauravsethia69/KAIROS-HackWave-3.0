# Test scenarios and reproduction

Tests use isolated fictional enterprise records and mocked external services, never production business-table writes. Fixed test date: 2026-10-11. All names/IDs in fixtures are test inputs, not verified employee identities.

| Acceptance request | Asserted behavior |
| --- | --- |
| Who owns the blocked SSO task? | Task `t1`, recorded employee owner, blocker `t2`, source evidence; no personal blame |
| Why is Atlas Media Group's reporting project delayed? | Project `p2`, recorded Delayed status, tasks and explicit causal uncertainty |
| Prepare for an OrbitPay client meeting | Client `orbit`, upcoming meeting `m1`, client context and communication |
| Show Engineering team workload | Department `eng`, recorded assignments, estimates and merged overlapping schedule blocks |
| Investigate declining product usage | UsageChart first, separate MetricCards, fixture period change -50%, no inferred cause |
| Summarize urgent support incidents | Urgent unresolved issue `i1`, recorded responder and SLA duration without invented breach time |
| Prepare a leadership briefing | Project/client/issue/meeting mix and contract status/renewal evidence |

Knowledge tests cover all 24 documents, metadata rejection, search ordering, source stability and missing documents. Generator test produces 90 synthetic employee/client/project briefs and checks repeatability and excluded fields. Responsibility tests cover owners, department/manager, task blockers, cycles and missing owners.

Intent/workspace tests cover all six primary intents, ownership and employee scope, partial/misspelled/ambiguous clients, actual candidate selection, unsupported goals, changed clients/goals, blocked and unresolved filters, dates/table layouts, invalid types/props/references, missing usage data, usage calculations, merged intervals and context expiry/isolation.

API/security tests cover every new endpoint without authentication, invalid token, unlinked/disabled membership, exact enabled-membership SQL condition and verified UUID parameter, unchanged auth/me shape, forged browser identity rejection, 400/404/422/503 responses, read-only transaction ordering, safe database errors, bounded allowlisted SELECTs, context isolation and no external AI invocation. Legacy backend tests remain included. Disabled and unlinked cases mock the common `None` authorization result; a separate SQL assertion verifies the enabled predicate.

Run from the project root:

```powershell
& .venv-kairos/Scripts/python.exe -m unittest discover -s backend/tests -v
node scripts/npm.mjs run test
node scripts/npm.mjs run build
```

Results and remaining live verification are recorded in `implementation-report.md`. Frontend build includes TypeScript validation. Tests are not proof of live Supabase policies, real employee login or production record completeness.
