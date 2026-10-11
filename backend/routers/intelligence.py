from functools import lru_cache
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, Depends, Query, Path, Response
from pydantic import BaseModel

from ..auth import Identity, current_user
from ..intelligence.context import contexts
from ..intelligence.evidence import resolve_evidence
from ..intelligence.intent import resolve_intent
from ..intelligence.knowledge import Knowledge, Metadata
from ..intelligence.models import EntityKind, EntityRef, Evidence, IntentRequest, ResolvedIntent, Workspace
from ..intelligence.repository import Snapshot
from ..intelligence.gateway import load_read_snapshot
from ..intelligence.profiles import profile_for_request
from ..intelligence.retrieval import SearchResponse, search
from ..intelligence.workspace import compose_workspace
from ..services.responsibility import Responsibility, find_employees, resolve

router = APIRouter(prefix='/api/intelligence', tags=['Deterministic enterprise intelligence'])


@lru_cache
def knowledge():
    return Knowledge()


def snapshot(user: Identity = Depends(current_user)):
    return load_read_snapshot(user)


def plan_snapshot(request: IntentRequest, user: Identity = Depends(current_user)):
    """Conservative intent-first table selection; follow-ups use full data."""
    profile, window = profile_for_request(request)
    return load_read_snapshot(user, profile=profile, usage_window=window, request_text=request.input)


class DocumentResponse(BaseModel):
    metadata: Metadata
    body: str
    sections: list[dict[str, str]]


class IntentResponse(BaseModel):
    intent: ResolvedIntent
    context_token: str


class EvidenceResponse(BaseModel):
    evidence: Evidence
    value: dict | str | int | float | bool | None


@router.get('/knowledge/search', response_model=SearchResponse)
def knowledge_search(q: str = Query(min_length=1, max_length=300), limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0, le=500),
                     department_id: str | None = Query(None, max_length=100), product_id: str | None = Query(None, max_length=100), entity_type: EntityKind | None = None,
                     category: Literal['company', 'departments', 'products', 'playbooks'] | None = None,
                     user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    return search(data, knowledge(), q, department_id=department_id, product_id=product_id, entity_type=entity_type, category=category, limit=limit, offset=offset)


@router.get('/knowledge/documents/{document_id}', response_model=DocumentResponse)
def document(document_id: str = Path(pattern=r'^[a-z0-9-]+$', max_length=100), user: Identity = Depends(current_user)):
    return knowledge().get(document_id)


@router.get('/employees/me', response_model=Responsibility)
def my_responsibilities(user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    return resolve(data, EntityRef(entity_type='employee', entity_id=user.employee_id))


@router.get('/employees/search')
def employees(q: str = Query(min_length=1, max_length=100), limit: int = Query(10, ge=1, le=50), user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    return {'items': find_employees(data, q, limit), 'limit': limit}


@router.get('/entities/{entity_type}/{entity_id}', response_model=Responsibility)
@router.get('/responsibility/{entity_type}/{entity_id}', response_model=Responsibility)
def entity(entity_type: EntityKind, entity_id: str = Path(pattern=r'^[A-Za-z0-9_-]+$', max_length=100), user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    return resolve(data, EntityRef(entity_type=entity_type, entity_id=entity_id))


@router.get('/evidence/{evidence_id}', response_model=EvidenceResponse)
def evidence(evidence_id: str = Path(pattern=r'^[A-Za-z0-9:_-]+$', max_length=250), user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    return resolve_evidence(evidence_id, data, knowledge())


@router.post('/intent/resolve', response_model=IntentResponse, response_model_exclude_none=True)
def intent(request: IntentRequest, user: Identity = Depends(current_user), data: Snapshot = Depends(snapshot)):
    result = resolve_intent(request, data, user, contexts.get(request.context_token, user))
    return IntentResponse(intent=result, context_token=contexts.put(result, user))


@router.post('/workspace/plan', response_model=Workspace, response_model_exclude_none=True)
def workspace(request: IntentRequest, response: Response, user: Identity = Depends(current_user), data: Snapshot = Depends(plan_snapshot)):
    started = perf_counter()
    result = resolve_intent(request, data, user, contexts.get(request.context_token, user))
    intent_ms = (perf_counter() - started) * 1000
    planning = perf_counter()
    plan = compose_workspace(data, knowledge(), result, request_text=request.input)
    compose_ms = (perf_counter() - planning) * 1000
    plan.context_token = contexts.put(result, user)
    # Only timing numbers. No prompts, identities, JWTs or SQL content leak.
    metrics = getattr(data, 'timings', {})
    cache_state = getattr(data, 'cache_state', 'BYPASS')
    # Deliberately no credentials, employee IDs, prompt text or SQL in headers.
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-KAIROS-Read-Cache'] = cache_state
    response.headers['Server-Timing'] = (
        f'snapshot;dur={data.load_ms:.1f}, cache;desc="{cache_state}";dur={metrics.get("cache_ms", 0.0):.1f}, '
        + ''.join(f'{key};dur={metrics[key]:.1f}, ' for key in (
            'db_pool_ms', 'db_setup_ms', 'db_sql_ms', 'db_fetch_ms', 'db_decode_ms') if key in metrics)
        + f'intent;dur={intent_ms:.1f}, compose;dur={compose_ms:.1f}'
    )
    return plan
