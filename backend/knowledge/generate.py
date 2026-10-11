"""Offline or explicitly authenticated read-only brief generation; no LLM usage."""
import argparse
import asyncio
import getpass
import hashlib
import json
from pathlib import Path

from fastapi.security import HTTPAuthorizationCredentials
from ..auth import current_user
from ..intelligence.catalog import RELATIONS, TABLE_ENTITY, title
from ..intelligence.models import EntityRef
from ..intelligence.repository import Snapshot, load_snapshot
from ..services.responsibility import resolve

DEFAULT_OUTPUT = Path(__file__).parent / 'generated'


def generate(snapshot: Snapshot, output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for table in ('employees', 'clients', 'projects'):
        for row in sorted(snapshot.rows(table), key=lambda r: r['id']):
            ref = EntityRef(entity_type=TABLE_ENTITY[table], entity_id=row['id'])
            relationship = resolve(snapshot, ref)
            payload = {'record': row, 'related': relationship.related, 'owner': relationship.owner, 'blocker_chain': relationship.blocker_chain}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
            metadata = {'id': f'brief-{ref.entity_type}-{row["id"]}', 'entity': ref.model_dump(), 'source_table': table,
                        'source_record_id': row['id'], 'generated_at': snapshot.retrieved_at.isoformat(), 'classification': 'private-generated',
                        'content_sha256': digest, 'authoritative': False, 'provenance': [e.model_dump(mode='json') for e in relationship.evidence]}
            path = output / f'{metadata["id"]}.md'
            body = '---\n' + json.dumps(metadata, indent=2) + '\n---\n# ' + title(row) + '\n\nSnapshot only. Live PostgreSQL remains authoritative.\n\n```json\n' + json.dumps(payload, indent=2, sort_keys=True, default=str) + '\n```\n'
            path.write_text(body, encoding='utf-8')
            manifest.append({'id': metadata['id'], 'path': path.name, 'content_sha256': digest})
    (output / 'manifest.json').write_text(json.dumps({'generated_at': snapshot.retrieved_at.isoformat(), 'authoritative': False, 'documents': manifest}, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--snapshot', type=Path, help='Operator-approved JSON snapshot; only explicitly allowlisted fields are read into briefs')
    mode.add_argument('--live', action='store_true', help='Verify an access token entered without echo, then read through existing employee permissions')
    args = parser.parse_args()
    if args.live:
        token = getpass.getpass('Supabase access token (not echoed or stored): ')
        user = asyncio.run(current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)))
        snapshot = load_snapshot(user)
    else:
        data = json.loads(args.snapshot.read_text(encoding='utf-8'))
        from datetime import datetime
        snapshot = Snapshot(data['tables'], retrieved_at=datetime.fromisoformat(data['retrieved_at']))
    documents = generate(snapshot)
    print(f'Generated {len(documents)} private briefs in ignored knowledge/generated; no database writes.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Brief generation failed. Check authorized source access; no credentials or connection details emitted.') from None
