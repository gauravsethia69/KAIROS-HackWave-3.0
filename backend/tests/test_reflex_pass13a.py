"""KAIROS Reflex v1: bounded, read-only, source-backed meeting counterfactuals."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import Identity, current_user
from backend.services import reflex
from backend.services.meeting_scheduler import MeetingProposal
from backend.main import app

USER = Identity(id=__import__('uuid').UUID('11111111-1111-4111-8111-111111111111'), employee_id='e1', access_role='employee')


def proposal(**changes):
    base = (datetime.now(timezone.utc)+timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    args = dict(title='Cross-team coordination', client_id='orbit', project_id=None, purpose='',
                starts_at=base, ends_at=base+timedelta(hours=1),
                participant_employee_ids=['e2'], idempotency_key=uuid4())
    args.update(changes)
    return MeetingProposal(**args)


def fake_preview(p, _user):
    conflict = p.starts_at == INITIAL
    return {
        'starts_at': p.starts_at.isoformat(), 'ends_at': p.ends_at.isoformat(),
        'can_create': not conflict, 'truncated': False,
        'conflicts': ([dict(employee_id='e1', employee_name='Employee A', source_type='meeting',
                            source_id='m1', title='Recorded appointment',
                            starts_at=(p.starts_at+timedelta(minutes=30)).isoformat(),
                            ends_at=(p.ends_at+timedelta(hours=1)).isoformat())] if conflict else []),
        'notice': 'Recorded overlap' if conflict else 'No recorded clash',
    }


INITIAL = None


class ReflexTests(unittest.TestCase):
    def setUp(self):
        global INITIAL
        self.p = proposal()
        INITIAL = self.p.starts_at

    def test_three_slots_and_conflict_aware_ranking(self):
        with patch.object(reflex, 'preview_meeting', side_effect=fake_preview) as preview, \
             patch.object(reflex, '_task_context', return_value={'visible_open_tasks':2}) as tasks:
            result = reflex.compare_meeting(self.p, USER)
        self.assertTrue(result['read_only'])
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual(result['candidates'][0]['rank'],3)
        self.assertEqual(result['candidates'][1]['rank'],1)
        self.assertEqual(result['candidates'][2]['rank'],2)
        self.assertEqual(result['candidates'][0]['affected_employee_count'],1)
        self.assertEqual(result['candidates'][0]['overlap_participant_hours'],0.5)
        self.assertEqual(preview.call_count,3)
        tasks.assert_called_once_with(USER, ['e1','e2'])

    def test_union_does_not_double_count_linked_bookings(self):
        a=self.p.starts_at
        rows = [dict(employee_id='e1', starts_at=a.isoformat(), ends_at=(a+timedelta(hours=1)).isoformat()),
                dict(employee_id='e1', starts_at=(a+timedelta(minutes=15)).isoformat(),
                     ends_at=(a+timedelta(minutes=45)).isoformat())]
        self.assertEqual(reflex._overlap_hours(rows,a,a+timedelta(hours=1)),1.0)
        rows.append(dict(employee_id='e2',starts_at=a.isoformat(),ends_at=(a+timedelta(minutes=30)).isoformat()))
        self.assertEqual(reflex._overlap_hours(rows,a,a+timedelta(hours=1)),1.5)

    def test_invalid_time_fails_before_any_database_access(self):
        invalid=proposal(starts_at=datetime.now(timezone.utc)-timedelta(days=1))
        with patch.object(reflex, 'preview_meeting') as preview, patch.object(reflex,'_task_context') as tasks:
            with self.assertRaises(HTTPException) as ctx:
                reflex.compare_meeting(invalid,USER)
        self.assertEqual(ctx.exception.status_code,422)
        preview.assert_not_called()
        tasks.assert_not_called()

    def test_task_context_filters_closed_and_keeps_estimates_separate(self):
        rows=[{'owner_employee_id':'e1','status':'Open','estimated_hours':3},
              {'owner_employee_id':'e2','status':'Blocked','estimated_hours':None},
              {'owner_employee_id':'e2','status':'Completed','estimated_hours':400}]
        class DB:
            def execute(self,sql,args):
                self_sql = ' '.join(sql.split()).lower()
                assert 'select' in self_sql and 'insert' not in self_sql and 'update' not in self_sql
                assert args == (['e1','e2'],)
                class Cursor:
                    def fetchall(_self): return rows
                return Cursor()
        @contextmanager
        def only_read_only(_user,read_only):
            self.assertTrue(read_only)
            yield DB()
        with patch.object(reflex,'user_connection',side_effect=only_read_only):
            result=reflex._task_context(USER,['e1','e2'])
        self.assertEqual(result['visible_open_tasks'],2)
        self.assertEqual(result['estimated_backlog_hours'],3)
        self.assertEqual(result['tasks_without_estimates'],1)
        self.assertIn('not calendar',result['notice'])

    def test_too_many_tasks_are_marked_incomplete(self):
        rows=[{'status':'Open','estimated_hours':1}] * 201
        class DB:
            def execute(self,sql,args):
                class Cursor:
                    def fetchall(_self):return rows
                return Cursor()
        @contextmanager
        def fake(_user,read_only):
            assert read_only
            yield DB()
        with patch.object(reflex,'user_connection',side_effect=fake):
            result=reflex._task_context(USER,['e1'])
        self.assertTrue(result['truncated'])
        self.assertEqual(result['visible_open_tasks'],200)

    def test_route_requires_auth(self):
        client=TestClient(app)
        response=client.post('/api/intelligence/scheduling/reflex/compare',json=self.p.model_dump(mode='json'))
        self.assertEqual(response.status_code,401)

    def test_route_is_read_only_comparison_not_confirmation(self):
        app.dependency_overrides[current_user]=lambda:USER
        try:
            with patch('backend.routers.scheduling.compare_meeting',return_value={'status':'compared','read_only':True}) as comp, \
                 patch('backend.routers.scheduling.confirm_meeting') as confirm:
                response=TestClient(app).post('/api/intelligence/scheduling/reflex/compare',json=self.p.model_dump(mode='json'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['read_only'],True)
            comp.assert_called_once()
            confirm.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_truncated_preview_never_ranked_clear(self):
        def preview(p,user):
            return {'starts_at':p.starts_at.isoformat(),'ends_at':p.ends_at.isoformat(),
                    'can_create':False,'truncated':True,'conflicts':[],'notice':'Incomplete'}
        with patch.object(reflex,'preview_meeting',side_effect=preview), \
             patch.object(reflex,'_task_context',return_value={}):
            result=reflex.compare_meeting(self.p,USER)
        self.assertTrue(all(not c['recorded_clear'] for c in result['candidates']))
        self.assertTrue(all(c['truncated'] for c in result['candidates']))


if __name__ == '__main__': unittest.main()
