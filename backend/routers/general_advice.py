"""Optional general business advice with existing Supabase employee authentication."""
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from ..auth import Identity, current_user
from ..intelligence.general_advice import advise, is_general_advice

router = APIRouter(prefix='/api/intelligence/general-advice', tags=['General AI guidance'])


class AdviceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input: str = Field(min_length=8, max_length=550)


@router.post('/answer')
def advice_answer(request: AdviceRequest, response: Response, user: Identity = Depends(current_user)):
    response.headers['Cache-Control'] = 'private, no-store'
    # No browser-provided facts/roles; all cost counters scoped to verified identity.
    return advise(request.input, viewer=f'{user.id}:{user.employee_id}:{user.access_role}')
