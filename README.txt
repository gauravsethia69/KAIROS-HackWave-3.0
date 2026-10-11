KAIROS — SAFE HERO IMAGE REPLACEMENT FOR CURRENT APP.TSX

Your current App.tsx imports KairosHeroScene from ../components/KairosHeroScene and renders <KairosHeroScene/>.
The previous Git patch expected older markup, which explains "patch failed".

This replacement makes NO edits to App.tsx at all.
It inserts a scoped CSS override that hides ONLY the decorative KairosHeroScene node in .page-heading, and shows a cropped, blended Fuji illustration instead.
Other routes, state, widgets, Supabase, backend, animations and business logic are unchanged.

TO INSTALL
1. Extract BOTH apply-kairos-current-fuji.cjs AND kairos-fuji-panel.png into C:\Hackwave 3.0 (the project root).
2. Open PowerShell there and run:
   node .\apply-kairos-current-fuji.cjs
3. Review changes:
   git diff -- src/styles/kairos-sakura-theme.css
   git status --short
4. Validate:
   npm.cmd run build
   npm.cmd run dev
5. Preview and check the desktop overview plus meeting and project workspaces.

It does not use `git apply` and will not fail on App.tsx line 18.
It safely refuses if it does not find <KairosHeroScene/>, if a conflicting previous override is present, or if the destination asset differs.
It is idempotent: a second run with matching asset reports already installed.

AFTER PREVIEW, SELECTIVE STAGING (be sure other CSS changes are not accidentally included):
   git add public/assets/kairos-fuji-panel.png
   git add -p src/styles/kairos-sakura-theme.css
   git diff --cached --stat
   git diff --cached
   git commit -m "style: upgrade KAIROS workspace hero artwork"

Do NOT add ZIP files, installer .cjs, environment files, or unrelated changes to the hackathon repository.

UNDO (if desired):
1. Restore your original CSS from the timestamped backup in .git/kairos-hero-backups/ OR remove only the block between KAIROS CURRENT HERO IMAGE markers.
2. Delete public/assets/kairos-fuji-panel.png if it is not used elsewhere.

If another theme overrides .page-heading after this stylesheet, an adjustment may be needed. Send a screenshot before committing.
