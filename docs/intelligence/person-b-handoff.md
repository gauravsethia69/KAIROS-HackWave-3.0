# Person B handoff

No frontend edits or database migrations are required to run the backend. Consuming the new enterprise plans requires a separate, nonvisual frontend integration. Existing sign-in, `/api/auth/me`, navigation and demo planner remain available.

## Endpoints

All endpoints below use the existing verified Supabase bearer token and enabled employee membership. Prefix `/api/intelligence`:

| Method/path | Input | Response |
| --- | --- | --- |
| GET `/knowledge/search` | `q`, optional `department_id`, `product_id`, `entity_type`, `category`, `limit`≤50, `offset`≤500 | `items`, `evidence`, `total`, pagination, limitations |
| GET `/knowledge/documents/{document_id}` | Stable manifest ID | Metadata, Markdown body, sections |
| GET `/employees/me` | No identity input | Responsibility response for verified employee |
| GET `/employees/search` | `q`, `limit`≤50 | Safe employee records and limit |
| GET `/entities/{entity_type}/{entity_id}` | Validated source reference | Safe record, recorded relationships, evidence |
| GET `/responsibility/{entity_type}/{entity_id}` | Same reference | Same relationship contract |
| GET `/evidence/{evidence_id}` | Stable evidence ID | Evidence descriptor and current value |
| POST `/intent/resolve` | `input`, optional `selection`, `context_token` | Normalized intent and continuation token |
| POST `/workspace/plan` | Same request | Workspace v2 |

Entity types: employee, department, client, product, project, task, issue, meeting, contract, communication, usage, schedule, activity. IDs are bounded alphanumeric/underscore/hyphen strings. Production IDs must be obtained from real responses. `/docs` and `/openapi.json` expose generated schemas.

## Integration steps

1. Keep the existing Supabase session/refresh and employee gate. Attach the current access token using the existing API client.
2. Add a separate v2 response parser; do not weaken v1 Zod or replace demo contracts. Read `workspace-contract.md` for registered widget/binding pairs.
3. Bind source records by selector and returned record IDs. Map fields without hardcoded Acme/Nova IDs or the demo date. Render server-provided claim categories; avoid generating new causal conclusions in the browser.
4. Preserve the returned `context_token` only for the signed-in session; clear it on logout. On expired-context 404, allow a fresh request. On clarification show actual candidates; resend the input with a selected candidate and token.
5. Add source viewers for the validated descriptors in `evidence-contract.md`. A candidate is not an authorization grant. Do not invent internal links that do not exist.
6. Surface `partial`, `not_found`, limitations and source label `deterministic-enterprise`. Keep demo fallback visibly labeled if API returns 503. Never label local fixtures as company data.
7. Capacity, contracts and detailed ownership need table/insight adapters. No new unsupported widget name was emitted. All UI text remains English; Japanese remains secondary app branding only.

401 means reauthenticate; 403 means unlinked/disabled employee; 404 means missing/invisible entity/document/context; 400 means unsupported evidence descriptor; 422 means invalid request schema; 503 means unavailable dependency. Existing request-body limit returns 413. Do not display raw backend exceptions.

## Database coordination

No schema proposal is necessary and no migrations/seeds/policies were changed. New reads use the existing authenticated role and transaction-local verified UUID in read-only transactions. Schema/FKs and grants were inspected read-only; actual employee-policy behavior has not been live-tested. Person B should validate representative authorized employees before enabling this UI. The service intentionally has no privileged business-data fallback when a policy hides data.

No new environment variables or Python dependencies. Existing DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and FRONTEND_ORIGIN are reused. Existing frontend VITE_API_BASE_URL/Supabase variables remain unchanged. AI credentials are neither needed nor used. Groq is out of scope.
