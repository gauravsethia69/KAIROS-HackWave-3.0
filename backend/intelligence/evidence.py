from datetime import datetime, timezone
from fastapi import HTTPException
from .catalog import FIELDS, ENTITY_TABLE, TABLE_ENTITY, title
from .models import EntityRef, Evidence, Navigation


class EvidenceSet:
    def __init__(self, snapshot):
        self.snapshot, self.items = snapshot, {}

    def database(self, table, row, field='record'):
        if table not in TABLE_ENTITY or (field != 'record' and field not in FIELDS[table]):
            raise ValueError('Unsupported evidence source')
        if self.snapshot.get(table, row.get('id')) is None:
            raise ValueError('Evidence must reference a visible record')
        ref = EntityRef(entity_type=TABLE_ENTITY[table], entity_id=str(row['id']))
        evidence_id = f'db:{table}:{ref.entity_id}:{field}'
        self.items[evidence_id] = Evidence(id=evidence_id, source_type='database', source_table=table, entity=ref, title=title(row), field=field,
            retrieved_at=self.snapshot.retrieved_at, navigation=Navigation(kind='entity_detail', entity=ref))
        return evidence_id

    def document(self, document, section=None):
        meta = document['metadata']
        if section and section not in [s['id'] for s in document['sections']]:
            raise HTTPException(404, 'Knowledge section not found')
        evidence_id = f'doc:{meta["id"]}:{section or "document"}'
        self.items[evidence_id] = Evidence(id=evidence_id, source_type='document', document_id=meta['id'], title=meta['title'], field=section or 'document',
            retrieved_at=datetime.now(timezone.utc), navigation=Navigation(kind='knowledge_document', document_id=meta['id'], section=section))
        return evidence_id


def resolve_evidence(evidence_id, snapshot, knowledge):
    parts = evidence_id.split(':')
    sources = EvidenceSet(snapshot)
    if len(parts) == 4 and parts[0] == 'db':
        _, table, entity_id, field = parts
        if table not in TABLE_ENTITY or (field != 'record' and field not in FIELDS[table]):
            raise HTTPException(400, 'Unsupported evidence descriptor')
        row = snapshot.entity(EntityRef(entity_type=TABLE_ENTITY[table], entity_id=entity_id))
        key = sources.database(table, row, field)
        return {'evidence': sources.items[key], 'value': row if field == 'record' else row.get(field)}
    if len(parts) == 3 and parts[0] == 'doc':
        _, document_id, section = parts
        document = knowledge.get(document_id)
        key = sources.document(document, None if section == 'document' else section)
        return {'evidence': sources.items[key], 'value': document if section == 'document' else next(s for s in document['sections'] if s['id'] == section)}
    raise HTTPException(400, 'Malformed evidence descriptor')
