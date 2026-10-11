# Architecture audit — 2026-10-11

## Verified local architecture

- React/Vite frontend: `src/app/Root.tsx` gates the workspace on Supabase session plus `/api/auth/me`; landing, employee modal and animations belong to Person B and remain untouched.
- `backend/auth.py:current_user` verifies bearer tokens via Supabase Auth, then `database.lookup_active_employee` checks `employee_access.auth_user_id` and `account_enabled IS TRUE`. Identity includes verified Auth UUID, employee ID and access role. Reuse this dependency on every new route; never accept these identity fields in request bodies.
- `database.user_connection` switches to `authenticated` and sets transaction-local JWT claims. `lookup_active_employee` is a separate trusted server lookup. Neither is replaced. New intelligence queries add READ ONLY transactions and use this existing restricted connection. Missing database grants return 503; there is no elevated-role fallback.
- Current REST repository returns the original seven demo tables; existing workspace-session writes remain existing functionality, never used by the new intelligence path.
- `services/planner.py` and `src/ai/planner.ts` share `src/ai/capabilities.json`. They know four demo intents and only Acme/Nova. They preserve request-supplied previous context. No independent Reflex service/module exists in the inspected source; extend this request-local context pattern rather than adding a competing state store.
- `services/ai.py` contains an earlier optional provider adapter. The new intelligence pipeline never imports or calls it. The active legacy route will be constrained to deterministic planning for this assignment; preserve its JSON shape.
- Widget registry has ten types: ClientProfile, MeetingBrief, UsageChart, MetricCards, ActivityTimeline, TaskList, ProjectProgress, IssuePanel, DataTable, InsightPanel. Widgets take a Dataset plus legacy plan, not arbitrary props. Frontend Zod is strict, schemaVersion 1, entity allowlist acme/nova. Enterprise responses therefore need an **additive versioned endpoint and documented nonvisual adapter**, not silent insertion of enterprise IDs into the legacy contract.
- Legacy date selectors use a fixed 2026-10-10 demo clock; enterprise intelligence must use explicit server dates and cannot reuse those calculations unmodified.
- Local migration contains only the early demo schema and does not describe employee/enterprise foreign keys. It is historical, not authoritative for the populated database. No migration or seed will be executed or edited. A read-only schema inspector is supplied to verify actual columns/FKs.
- Existing backend tests still instantiate Identity with UUID only; they predate employee authorization. Update mocked identities/membership in tests, never relax production authentication to satisfy stale fixtures.
- `backend/.venv` currently runs Python 3.11 but contains incompatible psycopg binaries. Existing `.venv-kairos` has working backend dependencies and is used for checks; no new packages are needed.

## Additive modules

`backend/intelligence/` holds typed contracts, explicit safe field catalogs, read-only repository, document loader/retrieval, intent resolution, workspace composition, and short-lived employee-bound context. `backend/services/responsibility.py` resolves recorded foreign keys. `backend/routers/intelligence.py` adds authenticated APIs. `backend/knowledge/` holds reviewed metadata and explicitly proposed operating procedures; generated briefs remain ignored private artifacts. Tests use isolated fictional enterprise fixtures.

Schema inspection findings and permission limitations are recorded in `implementation-report.md`; no data counts are claimed as live-verified from the prompt alone.
