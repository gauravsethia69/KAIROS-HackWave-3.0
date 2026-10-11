# KAIROS — Judge-ready Deployment Playbook

**Target:** Vercel (static React/Vite), Render (single always-on FastAPI web service), existing morph-ai Supabase PostgreSQL+Auth, optional Groq API. This kit contains no secrets and does not deploy or bill you automatically.

## 0. Freeze and protect the repo

1. Keep a local archive or tagged commit of the *last known fully working* project (not the 100 MB ZIP full of `.env`, `node_modules`, and `.git`).
2. Install this kit using `install_deployment_kit.py --preview` then `--install`.
3. From `C:\Hackwave 3.0`, run:

   ```powershell
   .\.venv-kairos\Scripts\python.exe scripts/deploy_preflight.py --strict
   .\.venv-kairos\Scripts\python.exe -m unittest discover -s backend/tests -v
   npm.cmd ci
   npm.cmd run typecheck
   npm.cmd run test
   npm.cmd run build
   git status --short
   git ls-files -- .env.local backend/.env
   git diff --cached --check
   ```

   Expected: successful tests/build and **no output** for the two private files in `git ls-files`. Do not upload or commit temporary employee credentials, full ZIPs, or `.env` files. Public Supabase *publishable* key is intended to be public; backend `DATABASE_URL` and Groq API key are not.
4. Update the GitHub `main` branch with **all application source** including the latest Atlas/Groq/meeting passes. GitHub currently has an older baseline. For a local repo with `origin` already configured:

   ```powershell
   git add .
   git status --short
   git diff --cached --check
   git commit -m "chore: freeze tested KAIROS judge deployment"
   git push origin main
   ```

   Re-run preflight before `git add .`; inspect `git status` and staged files first. Confirm GitHub contains `backend/intelligence/general_advice.py`, `backend/knowledge/atlas_index.json`, and `src/ai/generalAdvice.ts`. Note the exact commit SHA for rollbacks.

## 1. Backend first: Render

In [Render Dashboard](https://dashboard.render.com/): New → Web Service → your `KAIROS-HackWave-3.0` GitHub repo.

| Setting | Value |
| --- | --- |
| Language | Python 3 |
| Branch | `main` (freeze after smoke passes) |
| Root Directory | **Leave blank** (repo root) |
| Build | `pip install -r backend/requirements.txt` |
| Start | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` (liveness only) |
| Instance | **Paid always-on**, choose and confirm its billed rate yourself |

In Render Environment, configure these **server-only** values:

```text
PYTHON_VERSION=3.12.14
DATABASE_URL=<Supabase Connect -> Session Pooler URL, SSL required>
SUPABASE_URL=<YOUR_MORPH_AI_SUPABASE_URL>
SUPABASE_PUBLISHABLE_KEY=<YOUR_SUPABASE_PUBLISHABLE_KEY>
FRONTEND_ORIGIN=https://<YOUR-EXACT-FRONTEND>.vercel.app,http://localhost:5173,http://127.0.0.1:5173
KAIROS_GROQ_ENABLED=true
KAIROS_GROQ_RANK_OPERATIONS=false
GROQ_API_KEY=<PRIVATE_GROQ_API_KEY>
GROQ_MODEL=openai/gpt-oss-20b
KAIROS_GROQ_DAILY_CALL_LIMIT=60
KAIROS_GROQ_HOURLY_CALL_LIMIT=15
KAIROS_GROQ_DAILY_TOKEN_LIMIT=<YOUR_APPROXIMATE_PROCESS_BUDGET>
```

Be aware: Groq counters are **process-local**, reset after restarts, and are NOT a true account-wide money/token cap. Check Groq Console before judge sessions. Keep `AI_API_KEY` unused unless legacy live AI intentionally needs it.

Render logs should show import/startup success. The public `https://...onrender.com/health` endpoint must return `{"status":"ok","service":"kairos-api"}`. **This is only process liveness, not database or Groq readiness.** The API uses `psycopg` and transaction-local RLS claims, so authenticated DB smoke matters more than liveness alone.

**Avoid:** Setting Render Root Directory to `backend`, running `uvicorn main:app`, running `--reload` in production, SQLite migration, creating a new Supabase project, or pasting your `DATABASE_URL`/Groq key into Vercel.

## 2. Frontend: Vercel

In [Vercel Dashboard](https://vercel.com/new): import the same GitHub repo, Vite framework, root directory repo root, build `npm run build`, output `dist`. `vercel.json` provides SPA fallback for deep links. Set **production** environment variables:

```text
VITE_API_BASE_URL=https://<YOUR-RENDER-SERVICE>.onrender.com
VITE_SUPABASE_URL=https://<YOUR-MORPH-AI-PROJECT>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<YOUR-PUBLIC-SUPABASE-PUBLISHABLE-KEY>
```

**No trailing slash. HTTPS only.** Vite embeds `VITE_*` values at BUILD TIME, so a changed variable requires redeployment. Never put `GROQ_API_KEY`, `DATABASE_URL`, service-role keys or passwords in Vite variables.

Copy the exact Vercel **Production** URL and return to Render Environment → set `FRONTEND_ORIGIN` to that exact HTTPS origin (you may also retain localhost). Save/redeploy backend to apply CORS. Wildcards and partial domains are not supported by KAIROS's current CORS parser.

## 3. Supabase Auth URL configuration

Supabase Dashboard → Authentication → URL Configuration:
- Site URL = exact Vercel production origin (not localhost)
- Add production redirect `https://<your-vercel-domain>/**` and localhost development redirect if needed
- Use the **existing** employee accounts; validate at least two distinct employees.

No SQL migrations/seeding should be rerun. Verify `employee_access` links and enabled user permissions using existing app flows; never expose internal credentials in screenshots.

## 4. Public smoke tests (zero AI calls)

From local repo:

```powershell
.\.venv-kairos\Scripts\python.exe scripts/live_smoke.py --api https://<your-service>.onrender.com --web https://<your-app>.vercel.app
```

Expected: public health 200, unauthenticated endpoints 401, frontend 200.

**Manual browser checks, preferably two devices/networks:**
1. Open production URL in Chrome Incognito; landing, illustrations, fonts, gate animation render without errors.
2. Log in as Employee A. Verify `/api/auth/me` succeeds; 403 for unlinked users remains enforced. Sign out and repeat as Employee B, verifying employees have different authorized context.
3. `Show Engineering workload` → relevant employee/team view; inspect if it still incorrectly singles out Jordan Lee. **Do not present a wrong scope as validated.**
4. `Review delayed projects for Atlas Media Group` → authorized source-linked project facts and charts.
5. Meeting creation: preview a real occupied slot → conflict shown; try valid future slot → confirm after reviewing participants and final preview. Confirm exactly one meeting is written and visible to authorized attendees, retry same idempotency key safely.
6. `I am a new employee. How do things work?` → Atlas initially without Groq; request one explanation manually.
7. `How to increase sales?` → general Groq strategy panel. If budget low, test it once only; do not repeatedly retry.
8. Reload page and sign in again; use another device/network. Check no `localhost` API URLs in Network; all backend requests go over HTTPS.
9. Open browser DevTools → Console/Network: no CORS failures, `401` only for expected anonymous tests, no 502/503/timeout on normal load.

Keep HTTP request and response IDs or timestamps for debugging, NOT JWTs or secret strings.

## 5. Judge-day fail-safe runbook

- **Freeze:** do not merge changes into production after the final verified test; use git tag or known commit for rollback.
- **Backups:** check Supabase restore/backup options; Free Plan has limited recovery guarantees. Never reset existing production data.
- **One production Uvicorn worker** initially: cache and token budgets are process-local. Multiple instances invalidate single-process assumptions.
- **Health:** Monitor API `/health` from outside plus one authenticated manual flow. HTTP 200 from `/health` alone does not prove RLS/DB works.
- **If Groq fails:** keep deterministic charts and Atlas; explanation buttons must show fallback, not block workspace.
- **If API fails:** tell judges backend is temporarily unavailable; show previously prepared screen recording/screenshots and a local connected copy if the network allows. **Do not present stored screenshots as live data.**
- **If Vercel deploy fails:** redeploy previous verified deployment/commit. **If Render deploy fails:** use its rollback to last healthy revision. Recheck env and CORS after rollback.
- **2 hours prior:** sign in from phone + laptop, test one verified backend workflow and a single requested AI answer, keep both authenticated sessions, monitor usage.

## After launch — do not implement until judges can use the deployed app

1. **Counterfactual meeting impact simulator:** from a cross-department collision, compare alternative slots and invitee combinations by deterministic disruption score, preserving existing bookings. Only write after the organizer approves a proposal.
2. **Dependency ripple map:** trace `tasks.blocker_task_id` across projects and owners, surface which other team's milestones are impacted, with provenance; estimate impact ranges, not made-up deadlines.
3. **Evidence freshness radar:** surface whether a recommendation relies on old or incomplete records and compare before/after snapshots. No Groq required for source freshness.
