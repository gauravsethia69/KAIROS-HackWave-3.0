# FastAPI backend migration

Uses the existing **morph-ai** Supabase project for Auth and PostgreSQL. No project rename, schema replacement, new authentication provider or deployment is required by this change.

## Local setup (run from repository root)

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
backend/.venv/Scripts/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

On this machine, Python 3.12 is bundled rather than registered with `py`. The environment has already been created under `backend/.venv`. Use its Python directly. The bundled base executable is `C:/Users/WELCOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Its `ensurepip` is unavailable; installation can instead use `python -m pip --python backend/.venv/Scripts/python.exe install -r backend/requirements.txt` through the system pip.

Frontend, in a separate terminal:

```powershell
node scripts/npm.mjs run dev -- --host 127.0.0.1
```

Set root `.env`: `VITE_API_BASE_URL=http://localhost:8000`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY`. On environments with npm on PATH, standard `npm install` / `npm run dev` work. Auth still uses the Supabase browser client; all application data, saved sessions and connected planning use FastAPI.

Backend `backend/.env`: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `FRONTEND_ORIGIN`. AI is optional: `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`. No backend secrets belong in Vite variables. `FRONTEND_ORIGIN` is a comma-separated list of exact origins, such as `http://localhost:5173,http://127.0.0.1:5173,https://your-app.vercel.app`.

## PostgreSQL and access control

Reuse `supabase/migrations/202610100001_kairos.sql` and `supabase/seed.sql`. If already applied to morph-ai, **do not rerun the create-table migration**. No new SQL migration is needed. If not yet applied, apply the original migration once, then the idempotent seed. The `claim_ai_request` function from that migration is used for live AI rate limiting.

Copy the existing project's PostgreSQL session pooler connection URL (port 5432) from Supabase's Connect panel, with a URL-encoded password and `?sslmode=require`. Transaction pooler port 6543 also works with prepared statements disabled. Prefer `sslmode=verify-full` with an appropriate `sslrootcert` if a CA is available. The pool uses at most five connections; statement timeout is eight seconds. No SQLite fallback exists.

The database login must be able to `SET ROLE authenticated`. Every transaction switches to that restricted role and sets transaction-local `request.jwt.claim.sub` and `request.jwt.claims` from the **verified** user. Failure to assume the role fails closed. Prefer a dedicated login with membership in `authenticated` and no table-owner/BYPASSRLS privileges; otherwise the supplied privileged login is still downgraded for every business query. Session reads additionally contain an explicit `WHERE user_id = verified_user.id`; inserts derive user_id exclusively on the server. Request bodies cannot choose an owner. Never remove the role switch or ownership predicates.

Existing demo tables deliberately remain readable by all authenticated users, matching the existing RLS policies. They contain only fictional shared fixtures. Importing private real-company records requires tenant membership columns and policies; this migration does not pretend the demo schema is tenant-isolated.

Tokens are validated through Supabase Auth's `/auth/v1/user`, which validates their signature and expiration against the existing project's configuration. No unverified JWT decoding, passwords, or service-role keys are stored here. Invalid/expired tokens receive 401; verification outages receive 503. The browser refreshes once on a 401, then asks for sign-in.

## Endpoints

- Public: `GET /health` (liveness, not a database/provider readiness claim).
- Authenticated: `GET /api/clients`, `GET /api/clients/{id}`, `GET /api/clients/{id}/meetings`, `GET /api/clients/{id}/usage`.
- Authenticated: `GET /api/projects`, `GET /api/tasks` (optional `client_id` filter), `GET /api/communications`, `GET /api/issues`.
- Authenticated: `POST /api/workspace/plan`, `GET /api/workspace/sessions`, `POST /api/workspace/sessions`.

Planning accepts `{input, previous, use_ai:false}` and returns `{plan, source, message}`. Sources are `live`, `deterministic`, or `fallback`. Pydantic validates the same finite component, selector, entity and filter contracts as frontend Zod. Both deterministic planners use `src/ai/capabilities.json`. Browser demo planning stays local; connected planning runs in FastAPI. Local context changes never trigger provider calls. If FastAPI fails, the browser's existing local fallback remains available and labeled. Data failures remain visible; switch off Connected data to explicitly return to local fixtures.

Live AI requires `use_ai:true` plus configured credentials. `AI_BASE_URL` must be HTTPS; `/chat/completions` is appended. The provider must support JSON object output, temperature and max_tokens. Output is bounded and validated; calls have a 12-second overall provider deadline, with no agent loops or provider retries. Ten attempts/minute/account are enforced with the existing database RPC. Provider errors, invalid output or unavailable quota enforcement yield a labeled deterministic plan, not fake live success.

`supabase/functions/plan-workspace` is **legacy only**. Nothing in the frontend calls it anymore; it need not be deployed. Existing Edge tests remain for compatibility. Disable any previously deployed legacy function manually if no other client needs it. `supabase/config.toml` is retained as legacy local configuration and does not rename morph-ai.

## Render / Vercel

Render: Python 3.12 runtime (`PYTHON_VERSION=3.12.14`), **repository root** as working directory (the backend reads the shared frontend capability JSON). Build command `pip install -r backend/requirements.txt`. Start command `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Health path `/health`. Configure backend secrets and the explicit Vercel frontend origin. No GPU or background worker is needed.

Vercel: existing Vite build, `npm run build`, output `dist`; set the three Vite variables before building. Use the HTTPS Render URL for `VITE_API_BASE_URL`. No deployment has been performed.

## Tests

```powershell
backend/.venv/Scripts/python -m unittest discover -s backend/tests -v
node scripts/npm.mjs run test
node scripts/npm.mjs run build
```

Run backend tests first: they export three actual Pydantic plans to `artifacts/backend-plans.json`, which the frontend suite validates with Zod. Auth/provider/database tests use mocks; no paid provider or cloud database calls are made. Cloud verification still requires credentials and a two-account RLS/ownership check in morph-ai.
