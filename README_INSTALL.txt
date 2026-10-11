KAIROS — Entity Type Resolution Fix (backend only)
================================================
For C:\Hackwave 3.0 based on KAIROS_Hackwave_3.0_Latest_Synced.zip

Changed files:
  backend/intelligence/intent.py
  backend/tests/test_intelligence.py

No frontend, environment, credential, migration, or database changes.

INSTALL (PowerShell)
--------------------
1. Stop the existing FastAPI terminal with Ctrl+C. Leave React running.
2. Save this ZIP to your Downloads folder.
3. In a NEW PowerShell terminal, run:

$project = 'C:\Hackwave 3.0'
$zip = "$env:USERPROFILE\Downloads\KAIROS_Entity_Resolver_Fix.zip"
$backup = Join-Path $project ('artifacts\entity-resolver-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item "$project\backend\intelligence\intent.py" "$backup\intent.py"
Copy-Item "$project\backend\tests\test_intelligence.py" "$backup\test_intelligence.py"
Expand-Archive -LiteralPath $zip -DestinationPath $project -Force
Set-Location $project
.\.venv-kairos\Scripts\python.exe -m unittest discover -s backend/tests -v

4. After tests pass, start FastAPI again:

.\.venv-kairos\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

5. In KAIROS (already open), start a NEW request, without carrying over the
   old context token, then test:

   Who owns task t1?
   Who owns the blocked SSO task?
   Who owns the Northstar SSO readiness project?

EXPECTED
--------
t1 -> Jordan Lee (emp001), Operations rollout (p1), status Blocked;
      blocker_task_id is null, so the cause is not documented by that link.
p8 -> Hugo Laurent (emp012), Northstar Retail project, status On track.

Note: the type-selection regression tests were exercised in a mocked offline
environment. Full tests must be re-run on your PC with your working psycopg
installation, and real cloud responses must be verified separately.
