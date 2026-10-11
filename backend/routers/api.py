from fastapi import APIRouter, Depends

from ..auth import Identity, current_user
from ..schemas import Client, Meeting, Usage, Project, Task, Communication, Issue, PlanRequest, PlanResponse, SessionCreate, SessionRecord
from ..services import repository
from ..services.planner import local_plan

router = APIRouter(prefix='/api')


@router.get('/auth/me')
def authorized_employee(user: Identity = Depends(current_user)):
    # All fields come exclusively from the verified Supabase token and trusted database.
    return {'user_id': str(user.id), 'employee_id': user.employee_id, 'access_role': user.access_role}



@router.get('/clients', response_model=list[Client])
def clients(user: Identity = Depends(current_user)):
    return repository.records('clients', user)


@router.get('/clients/{client_id}', response_model=Client)
def client(client_id: str, user: Identity = Depends(current_user)):
    return repository.client(client_id, user)


@router.get('/clients/{client_id}/meetings', response_model=list[Meeting])
def meetings(client_id: str, user: Identity = Depends(current_user)):
    repository.client(client_id, user)
    return repository.records('meetings', user, client_id)


@router.get('/clients/{client_id}/usage', response_model=list[Usage])
def usage(client_id: str, user: Identity = Depends(current_user)):
    repository.client(client_id, user)
    return repository.records('product_usage', user, client_id)


@router.get('/projects', response_model=list[Project])
def projects(client_id: str | None = None, user: Identity = Depends(current_user)):
    return repository.records('projects', user, client_id)


@router.get('/tasks', response_model=list[Task])
def tasks(client_id: str | None = None, user: Identity = Depends(current_user)):
    return repository.records('tasks', user, client_id)


# Required by existing timeline and issue widgets; no extra product features.
@router.get('/communications', response_model=list[Communication])
def communications(user: Identity = Depends(current_user)):
    return repository.records('communications', user)


@router.get('/issues', response_model=list[Issue])
def issues(user: Identity = Depends(current_user)):
    return repository.records('issues', user)


@router.post('/workspace/plan', response_model=PlanResponse, response_model_exclude_none=True)
async def plan(request: PlanRequest, user: Identity = Depends(current_user)):
    # Preserve v1 response shape; external model calls are disabled for this phase.
    return PlanResponse(plan=local_plan(request.input, request.previous),
                        source='fallback' if request.use_ai else 'deterministic',
                        message='External AI is disabled. Deterministic planner used; enterprise intelligence is available at /api/intelligence/workspace/plan.')


@router.get('/workspace/sessions', response_model=list[SessionRecord], response_model_exclude_none=True)
def sessions(user: Identity = Depends(current_user)):
    return repository.sessions(user)


@router.post('/workspace/sessions', response_model=SessionRecord, response_model_exclude_none=True, status_code=201)
def save(request: SessionCreate, user: Identity = Depends(current_user)):
    return repository.save(request.plan, user)
