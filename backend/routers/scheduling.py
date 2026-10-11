"""Authenticated, auditable meeting-creation endpoints (no Groq)."""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from ..auth import Identity, current_user
from ..services.meeting_scheduler import (ConfirmMeeting, MeetingProposal,
                                          confirm_meeting, meeting_options, preview_meeting)

router = APIRouter(prefix='/api/intelligence/scheduling', tags=['Meeting scheduling'])


@router.get('/options')
async def options(user: Identity = Depends(current_user)):
    return await run_in_threadpool(meeting_options, user)


@router.post('/preview')
async def preview(request: MeetingProposal, user: Identity = Depends(current_user)):
    return await run_in_threadpool(preview_meeting, request, user)


@router.post('/confirm')
async def confirm(request: ConfirmMeeting, user: Identity = Depends(current_user)):
    return await run_in_threadpool(confirm_meeting, request, user)
