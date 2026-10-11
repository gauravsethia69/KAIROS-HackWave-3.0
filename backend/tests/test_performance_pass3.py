"""Read-scoping and v2-contract regressions. Uses mocks and synthetic fixtures only.

No live database access. SQL is verified as parameterized and conservatively
fallback-capable; Windows + Supabase verification remains necessary.
"""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from datetime import date

from backend.intelligence.catalog import FIELDS
from backend.intelligence.repository import (
    _read_scope, Snapshot, load_snapshot, WORKFLOW_PROFILES, DIRECT_TASK_TABLES,
)
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.intent import resolve_intent
from backend.intelligence.workspace import compose_workspace
from backend.intelligence.knowledge import Knowledge
from backend.tests.intelligence_fixtures import fixture, USER, TODAY


class PerformancePass3Tests(unittest.TestCase):
    def capture_query(self, **kwargs):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []

        @contextmanager
        def read(_user, *, timings=None):
            yield connection

        with patch('backend.intelligence.repository.read_connection', read):
            result = load_snapshot(USER, **kwargs)
        query, params = connection.execute.call_args.args
        return result, query.as_string(), params

    def test_exact_task_id_scope_is_narrow_and_parameterized(self):
        snapshot, query, parameters = self.capture_query(
            profile='ownership', request_text='Who owns task t1?')
        self.assertTrue(query.startswith('WITH RECURSIVE requested_task AS'))
        self.assertIn('FROM public.tasks WHERE id = %s', query)
        self.assertIn('blocker_chain', query)
        self.assertIn('WHERE id IN (SELECT id FROM blocker_chain)', query)
        self.assertIn('id IN (SELECT project_id FROM requested_task)', query)
        self.assertIn('id IN (SELECT client_id FROM requested_task)', query)
        self.assertNotIn('"issues"', query)
        self.assertNotIn('"contracts"', query)
        self.assertNotIn('"product_usage"', query)
        self.assertNotIn('employee_access', query)
        self.assertNotIn('password', query.lower())
        self.assertNotIn('t1', query)  # The actual ID is always a bound parameter.
        self.assertEqual(parameters[0], 't1')
        self.assertEqual(len(parameters), 1 + len(DIRECT_TASK_TABLES))
        self.assertEqual(len(snapshot.rows('tasks')), 0)

    def test_conservative_fallback_for_non_exact_task_and_full_profile(self):
        self.assertEqual(_read_scope('ownership', 'Who owns the blocked SSO task?'), (None, None))
        self.assertEqual(_read_scope('ownership', 'Who owns task t1 and project p1?'), (None, None))
        self.assertEqual(_read_scope(None, 'Who owns task t1?'), (None, None))
        self.assertEqual(_read_scope('meeting', 'Prepare for OrbitPay and Northstar Retail meetings'), (None, None))
        _, query, params = self.capture_query(profile='ownership', request_text='Who owns the blocked SSO task?')
        self.assertFalse(query.startswith('WITH RECURSIVE'))
        self.assertEqual(len(params), len(WORKFLOW_PROFILES['ownership']))

    def test_client_scope_uses_unique_name_match_or_unscoped_fallback(self):
        _, query, params = self.capture_query(profile='meeting', request_text="Prepare for tomorrow's OrbitPay client meeting")
        self.assertTrue(query.startswith('WITH matched_clients AS'))
        self.assertIn('POSITION(LOWER(name) IN LOWER(%s))', query)
        self.assertIn('(SELECT COUNT(*) FROM matched_clients) = 1', query)
        self.assertIn('NOT EXISTS (SELECT 1 FROM unique_client)', query)
        self.assertIn('meeting_id IN (SELECT id FROM public.meetings', query)
        self.assertNotIn('OrbitPay', query)
        self.assertEqual(params[0], "Prepare for tomorrow's OrbitPay client meeting")
        self.assertNotIn('"contracts"', query)
        self.assertEqual(len(params), len(WORKFLOW_PROFILES['meeting']) + 1)

    def test_scoped_usage_preserves_comparison_window(self):
        start, end = date(2026,9,14), date(2026,10,11)
        _, query, params = self.capture_query(profile='usage', usage_window=(start,end),
                                             request_text='Investigate product usage for OrbitPay')
        self.assertIn('"date" >= %s AND "date" <= %s', query)
        self.assertIn('"client_id" IN (SELECT id FROM unique_client)', query)
        self.assertEqual(params[0], 'Investigate product usage for OrbitPay')
        self.assertIn(start, params)
        self.assertIn(end, params)
        self.assertNotIn('OrbitPay', query)
        self.assertEqual(len(params),len(WORKFLOW_PROFILES['usage'])+3)

    def test_direct_task_scope_preserves_resolution_claims_and_references(self):
        full = fixture()
        table_subset = {
            'employees': full.rows('employees'),
            'departments': full.rows('departments'),
            'products': full.rows('products'),
            'clients': [r for r in full.rows('clients') if r['id']=='orbit'],
            'projects': [r for r in full.rows('projects') if r['id']=='p1'],
            'tasks': [r for r in full.rows('tasks') if r['id'] in ('t1','t2')],
        }
        scoped = Snapshot(table_subset)
        prompt='Who owns task t1?'
        baseline_intent=resolve_intent(IntentRequest(input=prompt),full,USER,today=TODAY)
        scoped_intent=resolve_intent(IntentRequest(input=prompt),scoped,USER,today=TODAY)
        self.assertEqual(baseline_intent.model_dump(),scoped_intent.model_dump())
        baseline=compose_workspace(full,Knowledge(),baseline_intent,today=TODAY)
        optimized=compose_workspace(scoped,Knowledge(),scoped_intent,today=TODAY)
        self.assertEqual([c.text for c in baseline.claims], [c.text for c in optimized.claims])
        self.assertEqual([c.type for c in baseline.components],[c.type for c in optimized.components])
        self.assertEqual(baseline.datasets['tasks'],optimized.datasets['tasks'])
        self.assertEqual(optimized.datasets['responsibilities'][0]['blocker_chain'][0]['blocking_task']['id'],'t2')
        Workspace.model_validate(optimized.model_dump())

    def test_named_client_scope_does_not_change_meeting_response_in_fixture(self):
        original = fixture()
        prompt="Prepare for tomorrow's OrbitPay client meeting"
        profile = WORKFLOW_PROFILES['meeting']
        filtered = {}
        matching_meetings={r['id'] for r in original.rows('meetings') if r['client_id']=='orbit'}
        for table in profile:
            if table == 'clients':
                filtered[table]=[r for r in original.rows(table) if r['id']=='orbit']
            elif table == 'meeting_participants':
                filtered[table]=[r for r in original.rows(table) if r['meeting_id'] in matching_meetings]
            elif 'client_id' in FIELDS[table]:
                filtered[table]=[r for r in original.rows(table) if r.get('client_id')=='orbit']
            else:
                filtered[table]=original.rows(table)
        full_profile=Snapshot({table:original.rows(table) for table in profile})
        scoped=Snapshot(filtered)
        a=resolve_intent(IntentRequest(input=prompt),full_profile,USER,today=TODAY)
        b=resolve_intent(IntentRequest(input=prompt),scoped,USER,today=TODAY)
        self.assertEqual(a.model_dump(),b.model_dump())
        first=compose_workspace(full_profile,Knowledge(),a,today=TODAY)
        second=compose_workspace(scoped,Knowledge(),b,today=TODAY)
        self.assertEqual([c.text for c in first.claims],[c.text for c in second.claims])
        self.assertEqual([c.type for c in first.components],[c.type for c in second.components])
        for key in ('clients','meetings','communications','issues','tasks','projects'):
            self.assertEqual(first.datasets.get(key), second.datasets.get(key), key)
        Workspace.model_validate(second.model_dump())

if __name__ == '__main__':
    unittest.main()
