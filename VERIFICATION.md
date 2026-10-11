# Verification — October 10, 2026

## FastAPI migration verification (current architecture)

- Created and tested a Python **3.12.14** environment in `backend/.venv`. Installed `backend/requirements.txt` using system pip's `--python` option because the bundled Python lacks working ensurepip. Installed direct dependency versions are now pinned.
- `backend/.venv/Scripts/python -m unittest discover -s backend/tests -v`: **16 tests passed**. Includes verified identity propagation, missing/invalid/expired tokens, explicit ownership, transaction-local restricted database role/claims, all three scenarios, context changes, strict schema rejection, provider failure/invalid-output fallback, body limits and CORS. Cloud dependencies mocked.
- `node scripts/npm.mjs run build`: **PASS**, including TypeScript validation. No UI/theme/widget changes; only necessary connected-mode orchestration and service changes.
- Real Uvicorn startup: **PASS**, localhost `127.0.0.1:8000`. Health is liveness only.
- Real `GET http://127.0.0.1:8000/health`: **HTTP 200**, `{"status":"ok","service":"kairos-api"}`.
- `node scripts/npm.mjs run test`: **57 tests passed**, three files, no skips. Includes the 48 preserved tests plus API authentication/refresh, owner-free session requests, offline demo behavior, server fallback labels and frontend Zod validation of the three Python-generated scenario plans. The first attempt failed before executing tests because the sandbox lost Vitest temporary files; the approved run outside that sandbox passed.
- Windows sandbox prevented asyncio's internal socket-pair initialization; backend tests and server were rerun with explicit approval outside the sandbox. Starlette emits an httpx TestClient deprecation warning; tests pass, and no redundant alternate HTTP library was installed.
- Real morph-ai Auth/PostgreSQL/RLS, migration execution and paid AI provider calls: **NOT RUN**, no credentials configured. SQL migrations/seed were preserved without replacement. Legacy Edge Function is no longer called by the frontend.

The sections below record the earlier frontend implementation checks; the backend setup guide is authoritative for the new architecture.

## Passed locally

- `npm install`: dependencies installed and locked in `package-lock.json`. The initial audit found three test-tool advisories; updating Vitest to 5.0.3 resolved them. The final installation audit reported **0 vulnerabilities**.
- `npm run build`: **PASS**. TypeScript project validation and Vite production build. Final output includes a 318.92 KB application chunk and a separate 385.87 KB chart chunk (96.24 KB and 112.86 KB gzip). No final build warning.
- `npm run typecheck`: **PASS**. The final build also repeated TypeScript validation after the last source changes.
- `npm run test`: **48 tests PASS** in two files. Intent/paraphrases, three scenarios, context, ambiguity, schema safety, data scoping, missing data, and mocked Edge request handling.
- `node --experimental-strip-types scripts/generate-seed.ts`: **PASS**, generated the separate SQL seed from the frontend dataset.
- `node scripts/smoke.mjs`: **PASS** in headless Microsoft Edge at desktop 1440×1080 and mobile 390×844. Used the existing bundled Playwright installation.
- Screenshot inspection: desktop overview, desktop usage, and mobile usage reviewed. Six screenshots are in `artifacts/` (ignored by Git).

The browser smoke test exercised all three scenarios, local task completion, 14-day filtering, prior-period comparison, chart ordering, chart-to-table replacement, table sorting, CSV download, unresolved issue filtering, client clarification, Nova meeting context, mobile horizontal-overflow checks, demo account guidance, and Ctrl+K. **No page errors.**

## Runtime details and actual commands

This machine has bundled Node 24.19.0, but npm was absent from PATH. Installation was bootstrapped with the bundled `pnpm --package=npm dlx npm install`. The resolved npm CLI was then invoked with Node for `run build`, `run test`, `run typecheck`, `audit --json`, and `run dev`. `scripts/npm.mjs` now resolves that CLI; final build and test used:

```sh
node scripts/npm.mjs run build
node scripts/npm.mjs run test
```

For browser testing on this machine:

```powershell
$env:PLAYWRIGHT_MODULE='C:/Users/WELCOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:PLAYWRIGHT_CHANNEL='msedge'
node scripts/smoke.mjs
```

Initial headless launches were blocked by the Windows sandbox and its isolated network. The successful run used an explicitly approved headless browser and a localhost-only Vite server outside the sandbox. An initial smoke-test heading locator was corrected to accept the browser's whitespace normalization, then the complete test passed twice, including after readability changes.

Live development server: **http://127.0.0.1:5173**. To restart it:

```sh
node scripts/npm.mjs run dev -- --host 127.0.0.1
```

## NOT RUN

No Supabase project credentials or AI provider credentials were supplied. Real email/signup/session behavior, database migration execution, RLS with two actual users, cloud persistence, deployed Edge runtime, and live model output have **NOT RUN**. Edge tests replace Deno, Supabase auth, the quota RPC and provider fetch with mocks; they do not prove cloud integration or SQL execution.

No AI calls, deployments, Git commits, pushes, or repository creation occurred. Demo mode is usable independently of all external integrations.
