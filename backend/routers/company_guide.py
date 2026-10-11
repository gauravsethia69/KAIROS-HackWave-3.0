"""Authenticated, PDF-only onboarding and company-reference guidance.

Separate API surface: existing /workspace/plan, DB gateway, and /atlas/search
are unchanged. No public endpoint, no database queries, no write actions.
"""
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from ..auth import Identity, current_user
from ..intelligence.company_guide import prepare_guide, enrich_guide

router = APIRouter(prefix='/api/intelligence/company-guide', tags=['SORYU company guide'])


class GuideRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input: str = Field(min_length=2, max_length=650)


@router.post('/sources')
def company_sources(request: GuideRequest, response: Response, user: Identity = Depends(current_user)):
    response.headers['Cache-Control'] = 'private, no-store'
    return prepare_guide(request.input)


@router.post('/explain')
def company_explanation(request: GuideRequest, response: Response, user: Identity = Depends(current_user)):
    response.headers['Cache-Control'] = 'private, no-store'
    return enrich_guide(request.input, viewer=f'{user.id}:{user.employee_id}:{user.access_role}')
