# Enterprise workspace contract v2

`POST /api/intelligence/workspace/plan` is additive. The legacy `/api/workspace/plan` keeps its v1 request/response shape and deterministic demo planner. Its `use_ai:true` now returns clearly labeled fallback; there is no active external planning path.

Request (Bearer token required):

```json
{"input":"Who owns the blocked SSO task?","selection":{"entity_type":"task","entity_id":"t1"}}
```

`t1` is a test fixture ID. Production selections must come from returned candidates/search results. Optional `context_token` continues a previous request. Unknown request fields, including claimed roles/employee identity, are rejected with 422. Input is capped at 2,000 characters.

The response contains:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | Always 2 |
| `source` | Always `deterministic-enterprise` |
| `status` | `ready`, `partial`, `clarification`, `not_found`, `unsupported` |
| `title`, `intent` | English title and normalized intent with selected entities/filters |
| `context_token` | Opaque employee-bound continuation |
| `components` | Validated registry type, stable ID, title, priority, order, size, props, evidence IDs, reason |
| `datasets` | Safe source records and explicitly calculated supporting datasets |
| `claims`, `evidence` | Grounded facts/calculations, uncertainty/proposals and resolvable provenance |
| `explanations`, `limitations` | Component selection, context changes and data gaps |
| `integration_requirements` | Unsupported presentation adapters needed from Person B |

Example component fragment:

```json
{"id":"TaskList-tasks","type":"TaskList","title":"Assignments and blockers","priority":10,"order":0,"size":"wide","props":{"selector":"tasks","record_ids":["t1"],"binding":"response.datasets"},"evidence_ids":["db:tasks:t1:record"],"reason":"Assignments and blockers supports recorded ownership using 1 visible records."}
```

Allowed types exactly reuse `backend.schemas.Component` and the frontend registry: ClientProfile, MeetingBrief, UsageChart, MetricCards, ActivityTimeline, TaskList, ProjectProgress, IssuePanel, DataTable, InsightPanel. Selector/component pairs reuse `BINDINGS`. No code/HTML/SQL props are accepted. Sizes: small, medium, wide. `order` is ascending; higher priority is more important. First component is wide. Type+selector IDs survive reordering. Every bound record and evidence reference must exist in the response. Empty widgets are omitted and explained.

Meeting plans prioritize meetings/client context/communications/issues; usage plans prioritize charts/metrics/related issues; delivery plans prioritize projects/tasks/activity; incident plans prioritize urgent unresolved issues/responders; workload plans prioritize assignments/projects; executive plans prioritize project/client/issue/meeting context. Available data changes the actual layout, not only the heading. Table requests convert only registered selector combinations.

`datasets.usage_metrics` compares mean daily active users in equal current/prior windows; missing days are not zero and coverage is reported. `capacity` reports recorded weekly capacity, open-task estimates, unknown estimates and merged schedule intervals. Unbooked capacity is not guaranteed availability. `contracts` contains status/renewal data, no financial amounts. `responsibilities` contains relationship responses. `insights` mirrors typed claims. These supplemental datasets do not introduce new widget types.

Database field catalogs are explicit in `intelligence/catalog.py`; Pydantic validates bindings/references. Source rows retain existing column names and nullability. There is no arbitrary browser-supplied props or SQL execution. `GET /openapi.json` supplies authoritative request and response schemas.

## Frontend compatibility boundary

The existing frontend v1 Zod client restricts entity IDs to Acme/Nova and widgets consume Dataset+legacy plan. Do not feed v2 into that validator. Person B must add a v2 parser and nonvisual data-binding adapter, using `record_ids` against `datasets[selector]`. Adapt enterprise timestamps and server claims rather than invoking demo-date selectors/calculations. Capacity/contracts/ownership evidence require table/insight/viewer adapters; the backend reports these needs explicitly. No visual components were changed in this assignment.
