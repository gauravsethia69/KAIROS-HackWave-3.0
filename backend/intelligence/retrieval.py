from pydantic import BaseModel
from .catalog import ENTITY_TABLE, OWNER_FIELDS
from .intent import entity_matches
from .evidence import EvidenceSet
from .models import Evidence, Navigation


class SearchHit(BaseModel):
    title: str
    score: float
    evidence_id: str
    navigation: Navigation
    status: str | None = None


class SearchResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[SearchHit]
    evidence: list[Evidence]
    limitations: list[str]


def search(snapshot, knowledge, query, *, department_id=None, product_id=None, entity_type=None, category=None, limit=10, offset=0):
    evidence, hits = EvidenceSet(snapshot), []
    department = snapshot.get('departments', department_id) if department_id else None
    product = snapshot.get('products', product_id) if product_id else None
    from fastapi import HTTPException
    if department_id and not department or product_id and not product:
        raise HTTPException(404, 'Filter entity missing or not visible')
    employee_ids = {r['id'] for r in snapshot.rows('employees') if r.get('department_id') == department_id} if department else None
    for kind in ([entity_type] if entity_type else ['client', 'product', 'department', 'employee', 'project', 'task', 'issue', 'meeting', 'contract']):
        for candidate in entity_matches(snapshot, query, kind):
            row = snapshot.entity(candidate.entity)
            table = ENTITY_TABLE[kind]
            if employee_ids is not None and not (kind == 'employee' and row['id'] in employee_ids or row.get(OWNER_FIELDS.get(table, 'employee_id')) in employee_ids or kind == 'department' and row['id'] == department_id):
                continue
            if product and not (row.get('product_id') == product_id or row.get('primary_product_id') == product_id or kind == 'product' and row['id'] == product_id):
                continue
            key = evidence.database(table, row)
            hits.append(SearchHit(title=candidate.label, score=candidate.score, evidence_id=key, navigation=evidence.items[key].navigation))
    tag = department['name'] if department else product['name'] if product else None
    for match in knowledge.search(query, category=category, tag=tag, limit=100)['items']:
        doc = knowledge.get(match['document_id'])
        key = evidence.document(doc, match['section'])
        hits.append(SearchHit(title=match['title'], score=min(1, match['score'] / 30), evidence_id=key, navigation=evidence.items[key].navigation, status=match['status']))
    hits.sort(key=lambda hit: (-hit.score, hit.evidence_id))
    page = hits[offset:offset + limit]
    return SearchResponse(total=len(hits), offset=offset, limit=limit, items=page, evidence=[evidence.items[h.evidence_id] for h in page], limitations=snapshot.limitations)
