# KAIROS / カイロス

**The right interface at the right moment.** Original HackWave 3.0 project for PS4, Intent-to-Interface.

> **Backend migration:** The active connected architecture is now **React → FastAPI → morph-ai PostgreSQL**, with Supabase Auth retained. Follow [backend/README.md](backend/README.md) for current setup, environment variables, endpoints and Render deployment instructions. The direct-Supabase/Edge instructions below describe the earlier architecture and are retained only as historical context; do not deploy the legacy Edge planner for the current app. Demo mode and the UI are unchanged.

## Run locally

Node.js **22.12+** (Node 24 recommended) and npm:

```sh
npm install
npm run dev
```

Open the localhost URL printed by Vite (normally `http://localhost:5173`). No credentials are needed. All UI text is English; Japanese text is secondary branding only.

On this Windows workspace, Node is bundled but npm is not on PATH. The included helper resolves the installed npm CLI. Use `node scripts/npm.mjs install` and `node scripts/npm.mjs run dev` here; it supports the same npm arguments. The verified running preview is `http://127.0.0.1:5173`.

```sh
npm run build       # TypeScript validation + production bundle
npm run test        # focused planner, schema and data tests
npm run typecheck
npm run preview    # serve the built bundle
```

The build output is `dist/`. For Vercel, use the Vite preset, build command `npm run build`, output `dist`. No deployment has been performed.

## Demo walkthrough

1. **Prepare me for tomorrow's client meeting with Acme Corp.** Profile, next meeting, communications, previous meeting records, issues, talking points, and task actions appear.
2. **Investigate why Acme Corp's product usage dropped.** The chart takes priority with usage metrics, activity, issues and evidence. Observations and hypotheses have separate labels and sources.
3. **Review projects that are falling behind schedule.** Projects below expected progress, overdue tasks, owners, blockers, actions and timeline appear across clients.

Try these follow-ups after the usage investigation:

- Show only the last 14 days.
- Move the usage chart to the top.
- Show this information as a table instead.
- Focus on unresolved issues.
- Compare this with the previous period.

Try **Prepare for a client meeting** from Overview to see clarification, then select a client. Ctrl/Cmd+K focuses the command field. Tables sort and export CSV, issue rows expand, the meeting brief copies to clipboard, and task check-offs work locally for the current browser session.

**Data clock:** all fictional records are anchored to **October 10, 2026**. “Tomorrow” in this reproducible demo means October 11. The date filter applies to dated history; upcoming meetings and open tasks are deliberately retained. Project risk compares actual versus expected progress. Daily-active-user averages are averages of measured days, not unique users over the whole period. Comparison uses the immediately preceding window. Missing values remain gaps.

## How adaptation works

`input → interpretation → context → capability scoring → Zod validation → scoped selectors → component registry → responsive grid`

- `src/ai/planner.ts`: deterministic intent recognition and paraphrases, context-preserving transformations, ambiguity handling, reusable capability weights.
- `supabase/functions/_shared/plan.ts`: shared strict Zod contract, finite component and selector allowlists, compatible bindings, unique IDs, bounded sizes and entity IDs.
- `src/data/`: coherent fixtures, repository boundary, entity/date scoping and calculated evidence.
- `src/components/widgets/registry.tsx`: ten reusable, typed widgets. Data access stays outside presentation components.
- `src/components/layout/Workspace.tsx`: validated layout renderer, loading/empty/error handling and widget recovery.

The planner selects components from a scored catalog rather than rendering three hardcoded dashboard pages. No model-generated code, SQL, HTML or JSX is executed. Explanations describe the recognized goal, scope, widget purpose, sources and changes. The fallback is intentionally bounded; unsupported goals request clarification instead of pretending to understand everything.

## Connect Supabase

1. Create your own Supabase project. Run `supabase/migrations/202610100001_kairos.sql` in the SQL editor, then run `supabase/seed.sql`. The seed is separate and idempotent. `npm run seed:generate` regenerates it from the same frontend fixtures.
2. Enable email/password authentication in Supabase Auth. Configure the site URL and allowed redirect URLs for localhost and, later, the chosen production URL. With email confirmations enabled, confirm signup email before signing in.
3. Copy `.env.example` to `.env` and set:

   ```env
   VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
   VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
   ```

4. Restart Vite, open the account panel, sign up/sign in, then enable **Connected data**. Reading Supabase data is explicit; failures show a retry action rather than silently substituting local data. Turn off Connected data to return to fixtures.
5. Use the save icon to save the current validated plan. **Saved workspaces** restores your most recent ten plans. Dataset records are read-only; task check-offs are local and are not persisted to Supabase.

All authenticated users may read the fictional demo tables; anonymous API access and client writes are denied. Workspace sessions use `auth.uid() = user_id` RLS for reads/inserts/updates/deletes. Composite foreign keys prevent cross-client project/task/issue mismatches. This shared-demo schema is **not** a multi-tenant schema for real customer data; tenant membership policies are needed before importing real records.

## Optional Live AI

No paid API call is made by default. You must configure your own provider and explicitly enable Live AI in the app. Providers may charge for calls.

Using an installed Supabase CLI, link your project and deploy:

```sh
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase functions deploy plan-workspace
```

Set these **server-side secrets only**, using the Supabase dashboard or `supabase secrets set --env-file PATH_TO_PRIVATE_ENV_FILE`:

```env
AI_API_KEY=YOUR_PROVIDER_SECRET
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=YOUR_CHOSEN_MODEL
```

`AI_BASE_URL` must be an HTTPS OpenAI-compatible API base; `/chat/completions` is appended. Choose a model supporting Chat Completions JSON object output, `max_tokens` and `temperature`. Provider differences or invalid responses trigger an explicitly labeled deterministic fallback. There is no automatic provider retry or agent loop. The model receives only the goal, bounded previous plan, allowed entities and schema—not database records or secrets.

The function explicitly validates bearer tokens with `auth.getUser`; `verify_jwt = false` in `supabase/config.toml` disables only the gateway's legacy check, **not application authentication**. It uses the platform's `SUPABASE_URL` and `SUPABASE_ANON_KEY`, never a service-role key. Input is bounded to 2,000 characters and 24 KB, output is schema-validated, provider calls time out after 12 seconds, and the frontend times out after 18 seconds. The SQL RPC enforces ten attempts per minute per signed-in account. Set provider spending limits as appropriate; this per-account rate limit is not a global cost cap.

## Verification and limits

Local build, tests and browser checks are recorded in `VERIFICATION.md`. **Cloud authentication, RLS on a real Supabase project, saved-session persistence, Edge deployment and paid-provider behavior have NOT RUN without credentials.** Never treat local unit tests as cloud verification.

For connected verification, use two accounts: confirm both can read fictional demo data, neither can modify it, account B cannot read or change account A's workspace rows, missing/invalid tokens receive 401, invalid schemas receive 400, missing AI configuration receives 503, and an unavailable provider produces a visible local fallback. Then test one explicitly authorized provider call and verify its label says Live AI.

No repository was created, no commits or pushes were made, and nothing was deployed.
