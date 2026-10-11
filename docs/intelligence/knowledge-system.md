# Company knowledge system

The manifest loads 24 English documents: five company references, seven proposed department guides, four product references and eight proposed operational playbooks. These are source files, not LLM output. `backend/knowledge/build_authored.py` reproduces them; edit that authoring source when intentionally regenerating. Normal server startup only reads the manifest and Markdown.

Each Markdown file starts with JSON metadata between `---` delimiters. Required fields: stable `id`, `title`, `category`, `status`, integer `version`, `updated_at`, `tags`, `sources`, `classification`, `author`. The loader rejects invalid metadata, duplicate IDs and paths outside the knowledge directory. `##` headings become stable section slugs. Preserve document IDs and heading slugs when revising referenced material.

`reference` describes schema/evidence conventions or verified product descriptions; it does not certify an approved company policy. `proposed` explicitly marks newly authored workflows, department responsibilities and escalation procedures pending company approval. Product descriptions were read from the existing product catalog; additional investigative guidance is labeled proposed. No client promises, achievements or causal explanations have been invented.

Search combines normalized keywords, exact document IDs, title/tag matches, bounded body matches and conservative fuzzy matching. Scores and tie ordering are deterministic; they are not probabilities. Mixed search also returns visible relational entities. Search supports department/product/entity/category filters, limit 1–50 and offset 0–500. It searches only a bounded snapshot and authored documents, never generated private briefs.

## Private brief generator

From the project root:

```powershell
& .venv-kairos/Scripts/python.exe -m backend.knowledge.generate --snapshot C:/approved-data/snapshot.json
```

The input is an operator-approved JSON object with `retrieved_at` (ISO timestamp) and `tables` (table names to record arrays). Do not use employee credential exports as input. Safe fields are selected by `intelligence/catalog.py`. The generator produces one brief per visible employee/client/project, with stable entity/source IDs, timestamp, related records, ownership, provenance and a content hash. The same snapshot yields identical output. A test generates 54 + 14 + 22 = 90 synthetic briefs; production counts are not asserted.

`--live` is an optional alternative. It prompts without echo for an existing Supabase access token, verifies it through the unchanged employee dependency and reads under that employee's database permissions. It does not create tokens or identities. No live brief generation was run during implementation.

Output defaults to ignored `backend/knowledge/generated/`. Keep that directory private and outside version control. Briefs are snapshots; live PostgreSQL remains authoritative. Existing files for entities no longer visible are not automatically deleted: operators must manage retention/access to private exports. No dependency or database object was added.
