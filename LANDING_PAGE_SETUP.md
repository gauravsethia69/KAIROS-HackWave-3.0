# KAIROS / カイロス — Employee landing page

## What's included

- Japanese-inspired landing page based on the supplied reference. The image asset in `public/images/` is cropped from the image provided for this task.
- Responsive navigation and task prompt bar; protected options open employee sign-in.
- Supabase email/password sign-in dialog; no public sign-up link or signUp call.
- Session check on startup; dashboard is rendered only for a valid Supabase session.
- Typed goal entered before login is retained in the workspace command bar after sign-in.
- No changes to FastAPI, PostgreSQL, SQL migrations, or existing business logic.

## Install

If using the **frontend-only patch ZIP**, extract it directly into the existing `C:\Hackwave 3.0` project folder, allowing it to replace only the paths in the ZIP. First copy or back up any frontend files actively edited by your teammate. **Do not overwrite Person B's database work.**

If using the complete project ZIP instead, extract it into a NEW folder. The ZIP intentionally excludes local `.env` values, virtual environments, `node_modules`, generated build files, and `.git`.

From PowerShell:

```powershell
cd 'C:\Hackwave 3.0'
# If .env.local already contains your correct values, keep it.
# Otherwise: Copy-Item .env.example .env.local
# Set URL/key in .env.local and leave your local FastAPI port as 8765.
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1
```

Set `.env.local`:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
VITE_API_BASE_URL=http://127.0.0.1:8765
```

Your existing Supabase project is still named **morph-ai**. There is no reason to rename it.

## Verify

1. Sign out of KAIROS (if signed in), and refresh `http://127.0.0.1:5173`.
2. You should see the cherry-blossom landing page, not the dashboard.
3. Click **Employee sign in**, enter credentials of a provisioned Supabase Auth user, and sign in.
4. You should see the existing KAIROS workspace. Refresh and confirm the session persists.
5. Sign out. The public landing page should return.
6. Ensure **Authentication > Providers > Email > Allow new users to sign up** is disabled in Supabase settings (the exact location may vary in the dashboard). Hiding a button alone is not a signup security control.
7. After Person B prepares employees and grants, add a backend-backed employee membership check and block inactive/unknown employees, even if they have valid Supabase sessions. Do not present auth-only gating as employee authorization.

## Validation

- TypeScript compilation: passed in the build environment.
- Full Vite production bundle: not verified here, because the uploaded Windows dependencies lack the Linux Rollup native package and the container cannot reach npm to install it. Run `npm.cmd run build` and `npm.cmd run test` on your Windows machine.
