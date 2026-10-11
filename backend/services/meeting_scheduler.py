"""Authorized meeting scheduling for SORYU SYSTEMS.

Pass 10A: explicit employee-approved creation with conservative conflict
blocking, NOT automatic rescheduling or conflict resolution. All availability
checks are fresh DB reads; writes execute one restricted SECURITY DEFINER RPC.
"""
from datetime import datetime, timedelta, timezone
from time import perf_counter
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, Field
from psycopg import Error

from ..auth import Identity
from ..database import user_connection
from ..intelligence.gateway import invalidate_snapshots

IST = ZoneInfo('Asia/Kolkata')


class MeetingProposal(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    client_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    project_id: str | None = Field(default=None, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    purpose: str = Field(default='', max_length=800)
    starts_at: datetime
    ends_at: datetime
    participant_employee_ids: list[str] = Field(default_factory=list, max_length=12)
    idempotency_key: UUID


class ConfirmMeeting(MeetingProposal):
    confirmed: bool = False


def _participants(proposal: MeetingProposal, user: Identity) -> list[str]:
    ids = {user.employee_id}
    for employee in proposal.participant_employee_ids:
        if not employee or len(employee) > 80 or not employee.replace('-', '').replace('_', '').isalnum():
            raise HTTPException(422, 'Invalid participant identifier')
        ids.add(employee)
    if len(ids) > 12:
        raise HTTPException(422, 'A meeting supports a maximum of 12 employees')
    return sorted(ids)


def _validate(proposal: MeetingProposal) -> None:
    if proposal.starts_at.tzinfo is None or proposal.ends_at.tzinfo is None:
        raise HTTPException(422, 'Meeting timestamps must include a time-zone offset')
    start = proposal.starts_at.astimezone(timezone.utc)
    end = proposal.ends_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if not now + timedelta(minutes=5) <= start <= now + timedelta(days=365):
        raise HTTPException(422, 'Meeting must start at least five minutes from now and within one year')
    if not timedelta(minutes=15) <= end - start <= timedelta(hours=4):
        raise HTTPException(422, 'Meeting duration must be between 15 minutes and 4 hours')
    if proposal.title.strip() != proposal.title or len(proposal.title.strip()) < 3:
        raise HTTPException(422, 'Meeting title cannot have surrounding whitespace')


def meeting_options(user: Identity) -> dict:
    with user_connection(user, read_only=True) as connection:
        staff = connection.execute('''
            SELECT e.id, e.full_name, e.department_id, d.name AS department,
                   e.job_title FROM public.employees e
            JOIN public.departments d ON d.id = e.department_id
            ORDER BY d.name, e.full_name LIMIT 100
        ''').fetchall()
        clients = connection.execute('''
            SELECT id, name FROM public.clients ORDER BY name LIMIT 100
        ''').fetchall()
        projects = connection.execute('''
            SELECT id, name, client_id FROM public.projects ORDER BY name LIMIT 100
        ''').fetchall()
    return {'current_employee_id': user.employee_id, 'employees': staff,
            'clients': clients, 'projects': projects, 'time_zone': 'Asia/Kolkata'}


def preview_meeting(proposal: MeetingProposal, user: Identity) -> dict:
    """Fresh, read-only conservative preview. Does NOT reserve a slot."""
    _validate(proposal)
    ids = _participants(proposal, user)
    start = proposal.starts_at.astimezone(timezone.utc)
    end = proposal.ends_at.astimezone(timezone.utc)
    with user_connection(user, read_only=True) as connection:
        employees = connection.execute('''
            SELECT e.id, e.full_name, d.name AS department FROM public.employees e
            JOIN public.departments d ON d.id = e.department_id
            WHERE e.id = ANY(%s::text[]) ORDER BY e.id
        ''', (ids,)).fetchall()
        if len(employees) != len(ids):
            raise HTTPException(422, 'One or more requested employees do not exist')
        client = connection.execute('SELECT id, name FROM public.clients WHERE id=%s',
                                    (proposal.client_id,)).fetchone()
        if client is None:
            raise HTTPException(422, 'Client not found')
        project = None
        if proposal.project_id:
            project = connection.execute('''SELECT id, name FROM public.projects
                WHERE id=%s AND client_id=%s''',
                (proposal.project_id, proposal.client_id)).fetchone()
            if project is None:
                raise HTTPException(422, 'Project does not belong to selected client')
        blocks = connection.execute('''
            SELECT b.id, b.employee_id, b.starts_at, b.ends_at, b.block_type,
                   b.description FROM public.employee_schedule_blocks b
            WHERE b.employee_id = ANY(%s::text[]) AND b.starts_at < %s AND b.ends_at > %s
            ORDER BY b.starts_at, b.id LIMIT 101
        ''', (ids, end, start)).fetchall()
        meetings = connection.execute('''
            SELECT DISTINCT m.id, m.title, m.starts_at, m.ends_at, e.id AS employee_id
            FROM public.meetings m
            JOIN public.employees e ON e.id = ANY(%s::text[])
            WHERE m.starts_at IS NOT NULL AND m.ends_at IS NOT NULL
              AND m.starts_at < %s AND m.ends_at > %s
              AND (m.organizer_employee_id = e.id OR EXISTS (
                SELECT 1 FROM public.meeting_participants mp
                WHERE mp.meeting_id=m.id AND mp.employee_id=e.id))
            ORDER BY m.starts_at, m.id, e.id LIMIT 101
        ''', (ids, end, start)).fetchall()
    names = {employee['id']: employee['full_name'] for employee in employees}
    conflicts = ([{'employee_id': r['employee_id'], 'employee_name': names[r['employee_id']],
                   'source_type': 'schedule_block', 'source_id': r['id'], 'title': r['description'],
                   'starts_at': r['starts_at'].isoformat(), 'ends_at': r['ends_at'].isoformat()} for r in blocks[:100]]
                 + [{'employee_id': r['employee_id'], 'employee_name': names[r['employee_id']],
                     'source_type': 'meeting', 'source_id': r['id'], 'title': r['title'],
                     'starts_at': r['starts_at'].isoformat(), 'ends_at': r['ends_at'].isoformat()} for r in meetings[:100]])
    # A conflict is a booking overlap, not a statement of absolute availability.
    truncated = len(blocks) > 100 or len(meetings) > 100
    return {
        'can_create': not conflicts and not truncated,
        'title': proposal.title,
        'client': client, 'project': project,
        'organizer_employee_id': user.employee_id,
        'participants': employees,
        'starts_at': start.isoformat(), 'ends_at': end.isoformat(),
        'time_zone': 'Asia/Kolkata', 'duration_minutes': int((end-start).total_seconds()/60),
        'conflicts': conflicts, 'truncated': truncated,
        'notice': ('Some booking records were omitted; creation is disabled' if truncated else
                   'Recorded bookings overlap; choose another time. Ranked alternatives come in the next pass' if conflicts else
                   'No overlapping bookings found in accessible records. This is not a guarantee of availability. A fresh check occurs when you confirm.'),
        'idempotency_key': str(proposal.idempotency_key),
    }


def confirm_meeting(request: ConfirmMeeting, user: Identity) -> dict:
    """User-confirmed transaction, enforced by restricted DB function.

    The SQL function acquires per-employee transaction locks and checks for
    overlaps again under those locks before writing meetings + participants +
    linked calendar blocks. It verifies the verified organizer's JWT identity
    and active employee membership *inside the DB* as defense in depth.
    """
    if not request.confirmed:
        raise HTTPException(422, 'Explicit meeting confirmation is required')
    _validate(request)
    ids = _participants(request, user)
    try:
        with user_connection(user, read_only=False) as connection:
            try:
                row = connection.execute('''
                    SELECT public.kairos_create_meeting_v1(
                        %s::text, %s::text, %s::text, %s::text,
                        %s::timestamptz, %s::timestamptz, %s::text[], %s::uuid
                    ) AS result
                ''', (request.title, request.client_id, request.project_id,
                      request.purpose, request.starts_at, request.ends_at,
                      ids, request.idempotency_key)).fetchone()
            except Error as err:
                if err.sqlstate == '23P01':
                    raise HTTPException(409, 'A participant has a recorded booking at this time. No meeting was created.') from None
                if err.sqlstate == '42501':
                    raise HTTPException(403, 'Meeting creation is not authorized for this employee') from None
                if err.sqlstate == '42883':
                    raise HTTPException(503, 'Scheduling database migration is not installed') from None
                if err.sqlstate in ('22023', '23503', '23514'):
                    raise HTTPException(422, 'Meeting details could not be validated') from None
                raise
    except HTTPException:
        raise
    # Invoked ONLY after the outer transaction context successfully commits.
    invalidate_snapshots()
    return {'status': 'created', 'meeting': row['result'], 'cache_invalidated': True,
            'message': 'Meeting created. Recorded calendars are now linked to the new booking.'}
