"""Separate authenticated document search endpoint; no DB search modifications."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from ..auth import Identity, current_user
from ..intelligence.atlas_retrieval import atlas

router = APIRouter(prefix='/api/intelligence/atlas', tags=['SORYU knowledge atlas'])


@router.get('/search')
def atlas_search(response: Response,
                 q: str = Query(min_length=2, max_length=300),
                 limit: int = Query(default=5, ge=1, le=10),
                 category: Literal['company', 'departments', 'products', 'playbooks'] | None = None,
                 user: Identity = Depends(current_user)):
    # Keep internal reference material behind the exact same auth gate as
    # other intelligence endpoints. Does not call the DB read snapshot.
    response.headers['Cache-Control'] = 'private, no-store'
    hits = atlas().search(q, limit=limit, category=category)
    return {'query': q, 'total': len(hits), 'items': hits,
            'authority': 'Reference-only; live PostgreSQL records supersede document snapshots'}
