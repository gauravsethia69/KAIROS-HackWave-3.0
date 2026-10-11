"""Pass 10A: preview, explicit approval, identity security, no dummy writes."""
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import current_user
from backend.main import app
from backend.services import meeting_scheduler as m
from backend.tests.intelligence_fixtures import USER


def payload(**updates):
    start = datetime.now(timezone.utc) + timedelta(days=4)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    d = {
        'title': 'OrbitPay delivery alignment', 'client_id': 'orbitpay',
        'project_id': None, 'purpose': 'Align Sales and Engineering',
        'starts_at': start.isoformat(),
        'ends_at': (start + timedelta(hours=1)).isoformat(),
        'participant_employee_ids': ['emp033'], 'idempotency_key': str(uuid4()),
    }
    d.update(updates)
    return d


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []
    def fetchone(self): return self.one
    def fetchall(self): return self.many


class FakeDb:
    def __init__(self, *, clashes=None, client=True, employees=True):
        self.clashes = clashes or []
        self.client = client
        self.employees = employees
        self.queries = []
    def execute(self, statement, parameters=()):
        sql = str(statement)
        self.queries.append((sql, parameters))
        if 'JOIN public.departments d' in sql and 'WHERE e.id = ANY' in sql:
            return FakeCursor(many=[
                {'id':USER.employee_id,'full_name':'Jordan Lee','department':'Engineering'},
                {'id':'emp033','full_name':'Grace Chen','department':'Sales'},
            ] if self.employees else [])
        if 'FROM public.clients WHERE id=' in sql:
            return FakeCursor(one={'id':'orbitpay','name':'OrbitPay'} if self.client else None)
        if 'FROM public.projects' in sql:
            return FakeCursor(one={'id':'p1','name':'Operations rollout'})
        if 'FROM public.employee_schedule_blocks b' in sql:
            return FakeCursor(many=self.clashes)
        if 'FROM public.meetings m' in sql:
            return FakeCursor(many=[])
        raise AssertionError('Unexpected query: '+sql[:100])


@contextmanager
def fake_context(db, user=None, read_only=False):
    assert read_only is True
    yield db


class MeetingSchedulerTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_organizer_is_always_derived_from_identity(self):
        request = m.MeetingProposal.model_validate(payload(participant_employee_ids=['emp033','emp033']))
        self.assertEqual(m._participants(request, USER), sorted([USER.employee_id,'emp033']))

    def test_time_zone_offset_is_required(self):
        data = payload(starts_at='2026-10-15T11:00:00')
        with self.assertRaises(HTTPException) as ex:
            m._validate(m.MeetingProposal.model_validate(data))
        self.assertEqual(ex.exception.status_code, 422)

    def test_rejects_invalid_duration(self):
        p = payload()
        start = datetime.fromisoformat(p['starts_at'])
        p['ends_at'] = (start + timedelta(minutes=5)).isoformat()
        with self.assertRaises(HTTPException):
            m._validate(m.MeetingProposal.model_validate(p))

    def test_rejects_invalid_participant_ids(self):
        request = m.MeetingProposal.model_validate(payload(participant_employee_ids=['x;DROP']))
        with self.assertRaises(HTTPException):
            m._participants(request, USER)

    def test_preview_is_read_only_and_does_not_write(self):
        db = FakeDb()
        with patch.object(m,'user_connection',side_effect=lambda user,read_only: fake_context(db,user,read_only)):
            r = m.preview_meeting(m.MeetingProposal.model_validate(payload()), USER)
        self.assertTrue(r['can_create'])
        self.assertEqual(len(r['participants']),2)
        self.assertIn('No overlapping bookings',r['notice'])
        self.assertTrue(all('INSERT' not in statement for statement, _ in db.queries))

    def test_preview_blocks_recorded_overlap(self):
        p = payload()
        dt = datetime.fromisoformat(p['starts_at'])
        db = FakeDb(clashes=[{
            'id':'sched-emp001-2','employee_id':USER.employee_id,'starts_at':dt,
            'ends_at':dt+timedelta(hours=1),'block_type':'Meeting','description':'Meeting — Engineering',
        }])
        with patch.object(m,'user_connection',side_effect=lambda user,read_only: fake_context(db,user,read_only)):
            r = m.preview_meeting(m.MeetingProposal.model_validate(p), USER)
        self.assertFalse(r['can_create'])
        self.assertEqual(r['conflicts'][0]['employee_name'],'Jordan Lee')

    def test_preview_invalid_client_rejected(self):
        with patch.object(m,'user_connection',side_effect=lambda user,read_only: fake_context(FakeDb(client=False),user,read_only)):
            with self.assertRaises(HTTPException) as ex:
                m.preview_meeting(m.MeetingProposal.model_validate(payload()), USER)
        self.assertEqual(ex.exception.status_code,422)

    def test_confirmation_requires_explicit_human_approval(self):
        request=m.ConfirmMeeting.model_validate(payload())
        with patch.object(m,'user_connection') as connection:
            with self.assertRaises(HTTPException) as ex:
                m.confirm_meeting(request, USER)
        self.assertEqual(ex.exception.status_code,422)
        connection.assert_not_called()

    def test_successful_confirmation_invalidates_after_transaction(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value={'result':{'id':'kairos-m-x','title':'OrbitPay delivery alignment'}}
        request=m.ConfirmMeeting.model_validate(payload(confirmed=True))
        with patch.object(m,'user_connection',side_effect=lambda user,read_only: fake_context_write(db, read_only)), patch.object(m,'invalidate_snapshots') as invalidate:
            response=m.confirm_meeting(request,USER)
        self.assertEqual(response['meeting']['id'],'kairos-m-x')
        self.assertEqual(db.execute.call_count,1)
        invalidate.assert_called_once_with()

    def test_http_routes_require_auth(self):
        client=TestClient(app)
        for path in ('/api/intelligence/scheduling/options','/api/intelligence/scheduling/preview','/api/intelligence/scheduling/confirm'):
            response=client.get(path) if path.endswith('options') else client.post(path,json=payload())
            self.assertEqual(response.status_code,401)

    def test_http_preview_requires_validated_employee(self):
        app.dependency_overrides[current_user]=lambda:USER
        try:
            with patch('backend.routers.scheduling.preview_meeting',return_value={'can_create':True}) as fn:
                response=TestClient(app).post('/api/intelligence/scheduling/preview',json=payload())
            self.assertEqual(response.status_code,200)
            self.assertTrue(fn.called)
        finally:
            app.dependency_overrides.clear()

    def test_replayed_idempotency_key_is_forwarded(self):
        req=m.ConfirmMeeting.model_validate(payload(confirmed=True))
        db=MagicMock()
        db.execute.return_value.fetchone.return_value={'result':{'id':'kairos-m-original','replayed':True}}
        with patch.object(m,'user_connection',side_effect=lambda user,read_only: fake_context_write(db, read_only)), patch.object(m,'invalidate_snapshots'):
            r=m.confirm_meeting(req,USER)
        self.assertTrue(r['meeting']['replayed'])
        args=db.execute.call_args.args[1]
        self.assertEqual(args[-1],req.idempotency_key)


@contextmanager
def fake_context_write(db, read_only):
    assert read_only is False
    yield db


if __name__=='__main__': unittest.main()
