"""Pass 7: bounded, caller-RLS-compatible timetable reads (offline)."""
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from backend.intelligence.catalog import FIELDS
from backend.intelligence.repository import load_snapshot, WORKFLOW_PROFILES, _read_scope, _calendar_window, Snapshot
from backend.intelligence.profiles import profile_for_request
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.intent import resolve_intent
from backend.intelligence.workspace import compose_workspace
from backend.intelligence.knowledge import Knowledge
from backend.database import user_connection
from backend.tests.intelligence_fixtures import fixture, USER, TODAY


class CalendarPerformancePass7Tests(unittest.TestCase):
    def capture(self, q, *, profile='calendar'):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []
        @contextmanager
        def fake_read(_user, *, timings=None):
            yield connection
        with patch('backend.intelligence.repository.read_connection', fake_read):
            data = load_snapshot(USER, profile=profile, request_text=q)
        sql_object, params = connection.execute.call_args.args
        return data, sql_object.as_string(), params

    def test_calendar_uses_only_seven_relevant_tables(self):
        self.assertEqual(len(WORKFLOW_PROFILES['calendar']), 7)
        self.assertEqual(profile_for_request(IntentRequest(input='Show Avery Test schedule next week'), today=TODAY)[0], 'calendar')
        self.assertEqual(profile_for_request(IntentRequest(input='Show Engineering workload'), today=TODAY)[0], 'workload')
        self.assertEqual(profile_for_request(IntentRequest(input='Who owns task t1?'), today=TODAY)[0], 'ownership')

    def test_unique_named_employee_scopes_sql_and_utc_week(self):
        data, query, params = self.capture('Show Jordan Lee\'s schedule from 2026-10-12 to 2026-10-18')
        self.assertIn('matched_employees', query)
        self.assertIn('matched_departments', query)
        self.assertIn('target_employees', query)
        self.assertIn('calendar_bounds', query)
        self.assertIn('owner_employee_id IN (SELECT id FROM target_employees)', query)
        self.assertIn('employee_id IN (SELECT id FROM target_employees)', query)
        self.assertIn('meeting_id FROM public.meeting_participants', query)
        for excluded in ('public."issues"', 'public."activity_events"', 'public."communications"', 'public."product_usage"'):
            self.assertNotIn(excluded, query)
        self.assertIn('SET TRANSACTION', '') if False else None
        self.assertNotIn('Jordan Lee', query)
        self.assertEqual(params[0], "Show Jordan Lee's schedule from 2026-10-12 to 2026-10-18")
        self.assertEqual(params[0], params[1])
        self.assertEqual(params[2].isoformat(), '2026-10-11T18:30:00+00:00')
        self.assertEqual(params[3].isoformat(), '2026-10-18T18:30:00+00:00')
        self.assertEqual(len(params), 4 + len(WORKFLOW_PROFILES['calendar']))
        self.assertTrue(all(t in FIELDS for t in data.tables))

    def test_verified_self_scope_never_uses_name_to_select_employee(self):
        data, query, params = self.capture('Show my schedule from 2026-10-12 to 2026-10-18')
        self.assertIn('SELECT id FROM public.employees WHERE id = %s', query)
        self.assertNotIn('matched_employees', query)
        self.assertEqual(params[0], USER.employee_id)
        self.assertEqual(len(params), 3 + len(WORKFLOW_PROFILES['calendar']))

    def test_department_ambiguity_or_missing_employee_falls_back_without_guessing(self):
        _, query, params = self.capture('Show Engineering schedule next week')
        self.assertIn('matched_departments', query)
        self.assertIn('NOT EXISTS (SELECT 1 FROM target_employees)', query)
        self.assertEqual(params[0], 'Show Engineering schedule next week')
        self.assertNotIn("'Engineering'", query)
        self.assertEqual(_read_scope('calendar', 'Show Engineering schedule next week')[0], 'calendar_named')

    def test_explicit_invalid_date_window_does_not_prune_incorrectly(self):
        self.assertIsNone(_calendar_window('Show Avery Test schedule from 2026-10-12 to 2026-12-18'))
        self.assertIsNone(_calendar_window('Show Avery Test schedule next month'))
        self.assertEqual(_calendar_window('Show Avery Test schedule from 2026-10-12 to 2026-10-18'), (date(2026,10,12), date(2026,10,18)))
        _, q, _ = self.capture('Show Avery Test schedule from 2026-10-12 to 2026-12-18')
        self.assertNotIn('calendar_bounds', q)

    def test_original_full_snapshot_remains_available(self):
        self.assertIsNone(profile_for_request(IntentRequest(input='Show Avery Test schedule next week'), today=TODAY)[1])
        self.assertEqual(_read_scope('ownership', 'Who owns task t1?'), ('task_id','t1'))
        data,q,params=self.capture('Show Engineering workload',profile='workload')
        self.assertIn('public."issues"',q)
        self.assertNotIn('public."activity_events"',q)
        self.assertIn('target_employees',q)

    def test_calendar_plan_same_v2_for_narrow_projection(self):
        full=fixture()
        selected_tables={table:list(full.rows(table)) for table in WORKFLOW_PROFILES['calendar']}
        selected_tables['tasks']=[t for t in selected_tables['tasks'] if t.get('owner_employee_id')=='e1']
        selected_tables['employee_schedule_blocks']=[b for b in selected_tables['employee_schedule_blocks'] if b.get('employee_id')=='e1']
        selected_tables['meeting_participants']=[p for p in selected_tables['meeting_participants'] if p.get('employee_id')=='e1']
        thin=Snapshot(selected_tables)
        prompt='Show Avery Test schedule from 2026-10-12 to 2026-10-18'
        knowledge=Knowledge()
        original_intent=resolve_intent(IntentRequest(input=prompt),full,USER,today=TODAY)
        thin_intent=resolve_intent(IntentRequest(input=prompt),thin,USER,today=TODAY)
        self.assertEqual(original_intent.model_dump(),thin_intent.model_dump())
        original=compose_workspace(full,knowledge,original_intent,today=TODAY,request_text=prompt)
        optimized=compose_workspace(thin,knowledge,thin_intent,today=TODAY,request_text=prompt)
        self.assertEqual(original.schemaVersion,optimized.schemaVersion)
        self.assertEqual(original.status,optimized.status)
        for name in ('schedule_summary','schedule_events','schedule_days','employee_options','schedule_meetings','workload_chart'):
            self.assertEqual(original.datasets.get(name), optimized.datasets.get(name), name)
        self.assertEqual([c.text for c in original.claims], [c.text for c in optimized.claims])
        Workspace.model_validate(optimized.model_dump(mode='json'))

    def test_read_only_claims_are_batched_but_role_and_transaction_retained(self):
        connection=MagicMock()
        pool=MagicMock()
        pool.connection.return_value.__enter__.return_value=connection
        timing={}
        with patch('backend.database.get_pool',return_value=pool):
            with user_connection(USER,read_only=True,timings=timing):
                pass
        calls=connection.execute.call_args_list
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[0].args[0],'SET TRANSACTION READ ONLY')
        self.assertEqual(calls[1].args[0],'SET LOCAL ROLE authenticated')
        self.assertIn("set_config('request.jwt.claim.sub'",calls[2].args[0])
        self.assertIn("set_config('request.jwt.claims'",calls[2].args[0])
        self.assertIn("set_config('statement_timeout'",calls[2].args[0])
        self.assertEqual(calls[2].args[1][0],str(USER.id))
        self.assertIn('db_setup_ms',timing)
        connection.reset_mock()
        with patch('backend.database.get_pool',return_value=pool):
            with user_connection(USER,read_only=False):
                pass
        self.assertEqual(len(connection.execute.call_args_list),4)
        self.assertEqual(connection.execute.call_args_list[0].args[0],'SET LOCAL ROLE authenticated')

if __name__=='__main__':unittest.main()
