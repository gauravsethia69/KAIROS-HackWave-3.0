from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import settings

bearer = HTTPBearer(auto_error=False)


class Identity(BaseModel):
    # Supabase Auth verified UUID. Never trust an employee ID/role from requests.
    id: UUID
    employee_id: str
    access_role: str


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Identity:
    unauthorized = HTTPException(401, 'Invalid or expired access token', headers={'WWW-Authenticate': 'Bearer'})
    if not credentials or credentials.scheme.lower() != 'bearer' or len(credentials.credentials) > 8192:
        raise unauthorized
    if not settings.supabase_url or not settings.supabase_key:
        raise HTTPException(503, 'Authentication service is not configured')
    try:
        # Supabase Auth checks the token signature and expiry remotely. No unverified
        # JWT decoding, caller-provided employee IDs, or caller-provided roles.
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f'{settings.supabase_url}/auth/v1/user', headers={
                'apikey': settings.supabase_key, 'Authorization': f'Bearer {credentials.credentials}',
            })
        if response.status_code in (401, 403):
            raise unauthorized
        if response.status_code != 200:
            raise HTTPException(503, 'Authentication service unavailable')
        verified_user_id = UUID(response.json()['id'])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Authentication verification unavailable') from None

    # employee_access is intentionally not readable by the authenticated DB role.
    # This is an independent server-side check with the trusted PostgreSQL pool.
    from .database import lookup_active_employee
    membership = await run_in_threadpool(lookup_active_employee, verified_user_id)
    if membership is None:
        raise HTTPException(403, 'Employee access not authorized')
    return Identity(id=verified_user_id, employee_id=membership['employee_id'],
                    access_role=membership['access_role'])
