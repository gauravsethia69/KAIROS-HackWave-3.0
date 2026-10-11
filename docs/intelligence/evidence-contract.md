# Evidence and source navigation

Evidence is deduplicated by stable source identity, not generated prose. Database IDs follow `db:<table>:<record ID>:<field or record>`; document IDs follow `doc:<document ID>:<section or document>`. Retrieval timestamps change on refresh, while references remain stable.

```json
{"id":"db:tasks:t1:status","source_type":"database","source_table":"tasks","entity":{"entity_type":"task","entity_id":"t1"},"title":"Validate SSO callback fix","field":"status","retrieved_at":"2026-10-11T00:00:00Z","navigation":{"kind":"entity_detail","entity":{"entity_type":"task","entity_id":"t1"}}}
```

This example uses isolated fixture data. Claims are `observation`, `calculation`, `uncertainty` or `proposed_action`. Observations/calculations require evidence; every referenced evidence ID must resolve inside the plan. A delayed project status is evidence of status only. Dependency links establish recorded relationships, not causation. Procedures and escalation suggestions are explicitly proposed.

## Approved viewer contracts

| Descriptor | Authenticated resolution |
| --- | --- |
| `entity_detail` + validated entity | `GET /api/intelligence/entities/{entity_type}/{entity_id}` |
| `knowledge_document` + document ID and optional section | `GET /api/intelligence/knowledge/documents/{document_id}`; select the returned section slug |
| Evidence ID | `GET /api/intelligence/evidence/{evidence_id}` → `evidence`, `value` |

No clickable browser route is invented. Person B must connect descriptors to an internal viewer; URLs are not supplied by the planner. Source resolution repeats current authorization and database reads. A disappeared/invisible row returns 404, and a refreshed value may differ from an earlier observation. Unsupported source tables/fields return 400, malformed path parameters 422.

Employee email, auth/membership attributes, raw event metadata, schedule descriptions and contract financial amounts are excluded from the new snapshot field allowlist. Generated private briefs are not search sources. Existing authenticated-role policies determine row visibility; the new service does not grant additional department access. Policy correctness under real employee sessions still requires an authorized live integration check.
