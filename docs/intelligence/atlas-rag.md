# KAIROS / SORYU — Atlas Reference Retrieval (Pass 12A)

This is an **additive, separate, read-only reference retrieval channel** for the 24-page SORYU SYSTEMS Knowledge Atlas PDF. It does **not** replace or intercept either the existing DB-backed enterprise search (`backend/intelligence/retrieval.py`) or the authored knowledge engine (`backend/intelligence/knowledge.py`). No database schema, Supabase policies, migrations, authentication logic, frontend code, meeting logic, or existing planner behavior are changed.

## Why this is separate

The PDF explicitly identifies **morph-ai PostgreSQL as authoritative** for current employees, department membership, client/product ownership, meetings, schedules, work status and usage. The atlas contains 24 author-written references and proposed playbooks; it is not a current snapshot of every live row. Source status is carried into every chunk: `reference` or `proposed` (NOT approved policy). Treat its text as untrusted cited source material, never as tool instructions or permissions.

## What gets indexed

The offline script `scripts/build_atlas_index.py` parses the supplied PDF with PyMuPDF and indexes **103 small, section-level passages** from all 24 pages. Each passage has a stable ID, page number, 24-document source ID, heading, title, category, update date, status and PDF SHA-256. Repeated headers, footer and example prompts are not included as source passages. Runtime search loads **one local JSON file** and requires no embeddings subscription, model download, external API, SQL or extra Python package.

## Search it (authenticated)

With FastAPI running and a Supabase Auth bearer token already available to the frontend:

`GET /api/intelligence/atlas/search?q=Engineering%20workload&limit=5`

Users must be authenticated by the existing `current_user` dependency; it verifies both Supabase Auth identity and active employee membership. The endpoint returns citeable matching passages and `Cache-Control: private, no-store`. It does **not** change `/api/intelligence/knowledge/search` or `/api/intelligence/workspace/plan`. Use your existing frontend token flow; never paste the actual bearer token into source code or terminal logs/screenshots.

## Local test (no credentials)

```powershell
cd "C:\Hackwave 3.0"
.\.venv-kairos\Scripts\python.exe -m unittest backend.tests.test_atlas_retrieval -v
.\.venv-kairos\Scripts\python.exe -m backend.intelligence.atlas_retrieval "prepare OrbitPay client meeting"
```

The second command prints the top matches and bounded Groq-ready context locally without making any API call. Do not post sensitive text publicly.

## How Pass 12 Groq should use it

```python
from backend.intelligence.atlas_retrieval import groq_reference_context
result = groq_reference_context(user_question, max_chars=3600, limit=5)
reference_context = result['text']
source_citations = result['citations']
# Use only as REFERENCE context alongside the ALREADY PERMISSION-CHECKED live data
# assembled by the current backend. Groq plans; deterministic backend validates.
```

No Groq calls are made in Pass 12A. When Groq is integrated, the existing DB search and authenticated workspace resolver must remain the authoritative route for factual record lookups. The atlas context is optional, is under 3600 chars by default, and may return no matching passages. Groq must never use the atlas to invent IDs, statuses, attendance, organizational approvals, live dates or user access permissions.

## Regenerating if the PDF changes

Only the offline **rebuild** requires PyMuPDF (`python -m pip install pymupdf`). Example:

```powershell
.\.venv-kairos\Scripts\python.exe scripts\build_atlas_index.py "C:\path\to\SORYU_SYSTEMS_24_Page_Knowledge_Atlas.pdf"
```

Review the resulting index before committing. An update that changes source document count or PDF layout may require adjusting the builder.

## Safe install and rollback

The installer shows a read-only preview first, refuses to overwrite edited target files, backs up `backend/main.py` under `.kairos-backups/`, and modifies `main.py` **only by adding two route registration lines**. To roll back, stop the server, restore that backed-up `main.py`, then delete only the six new files listed by the installer. No database restoration is necessary because the add-on does not touch the database.
