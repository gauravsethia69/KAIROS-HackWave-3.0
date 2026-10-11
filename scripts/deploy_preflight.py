#!/usr/bin/env python3
"""Read-only preflight: verify deployment-critical files and tracked-file hygiene.
No config secrets are read, printed or transmitted. No network requests.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    'backend/main.py', 'backend/auth.py', 'backend/database.py',
    'backend/routers/intelligence.py', 'backend/routers/scheduling.py',
    'backend/routers/company_guide.py', 'backend/routers/general_advice.py',
    'backend/intelligence/atlas_retrieval.py', 'backend/intelligence/general_advice.py',
    'backend/intelligence/ai_usage.py', 'backend/knowledge/atlas_index.json',
    'backend/services/meeting_scheduler.py', 'backend/requirements.txt',
    'src/app/Root.tsx', 'src/app/App.tsx', 'src/ai/generalAdvice.ts',
    'src/lib/api.ts', 'src/lib/supabase.ts', 'package.json',
    'package-lock.json', 'vercel.json', '.github/workflows/kairos-ci.yml',
]


def unsafe_tracked(path):
    p = path.replace('\\', '/').lower()
    name = p.split('/')[-1]
    if name == '.env' or (name.startswith('.env.') and not name.endswith('.example')):
        return True
    if name.endswith(('.pyc', '.pyo', '.tsbuildinfo', '.key', '.pem', '.p12')):
        return True
    if name in ('id_rsa', 'id_ed25519'):
        return True
    if name.endswith('.zip') and ('credentials' in p or 'private' in p or 'employee' in p):
        return True
    if 'temporary_employee_credentials' in p or 'soryu_54_temporary' in p:
        return True
    if any(part in p.split('/') for part in ('node_modules', '.venv', '.venv-kairos', 'dist', '.kairos-backups', '__pycache__')):
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict', action='store_true', help='Fail if Git unavailable')
    args = parser.parse_args()
    errs = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errs.append(f'MISSING essential source: {rel}')
    git = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True)
    if git.returncode:
        if args.strict:
            errs.append('Git file audit unavailable; run this inside your Git checkout.')
        else:
            print('WARN: Git audit unavailable; run from actual Git checkout before deployment.')
    else:
        tracked = [p.decode('utf-8', 'replace') for p in git.stdout.split(b'\x00') if p]
        for path in tracked:
            if unsafe_tracked(path):
                errs.append(f'PRIVATE/GENERATED FILE TRACKED: {path}')
        # Catch files `git add .` would pick up, before anyone stages them.
        pending = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True)
        if pending.returncode == 0:
            for raw in pending.stdout.split(b'\x00'):
                if raw:
                    path = raw.decode('utf-8', 'replace')
                    if unsafe_tracked(path):
                        errs.append(f'UNIGNORED PRIVATE/GENERATED FILE: {path}')
    for rel in ('.env.local', 'backend/.env'):
        if (ROOT / rel).exists():
            print(f'PRIVATE LOCAL ENV PRESENT: {rel} (expected locally; must NEVER be committed)')
    for rel in ['backend/.env', '.env.local']:
        ignore = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', rel], capture_output=True)
        if not git.returncode and ignore.returncode != 0:
            errs.append(f'GITIGNORE MISCONFIGURED: {rel} is not ignored')
    if errs:
        for e in errs: print('FAIL:', e)
        print(f'PRECHECK FAILED ({len(errs)} issue(s)) — DO NOT DEPLOY')
        return 1
    print('PRECHECK OK: source files present; no unsafe tracked paths found.')
    print('NOTE: This is a path-level check, not a historical secret scan. Review Git history separately.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
