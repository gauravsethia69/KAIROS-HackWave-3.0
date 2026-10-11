"""Read profile and observability regressions; no Supabase/cloud dependency."""
import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import current_user
from backend.main import app
from backend.intelligence.catalog import FIELDS
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.intent import resolve_intent
from backend.intelligence.workspace import compose_workspace
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.repository import Snapshot, load_snapshot, WORKFLOW_PROFILES
from backend.intelligence.profiles import profile_for_request
from backend.routers.intelligence import plan_snapshot
from backend.tests.intelligence_fixtures import fixture, USER, TODAY


class PerformancePass2Tests(unittest.TestCase):
    CASES = [
        ("Prepare for tomorrow's OrbitPay client meeting", 'meeting'),
        ('Investigate product usage for Northstar Retail', 'usage'),
        ("Why is Atlas Media Group's reporting project delayed?", 'projects'),
        ('Summarize urgent support incidents', 'incidents'),
        ('Show Engineering workload', 'workload'),
        ('Prepare an executive briefing', 'executive'),
        ('Who owns task t1?', 'ownership'),
    ]

    def test_all_scenarios_choose_conservative_profiles(self):
        for query, expected in self.CASES:
            with self.subTest(query=query):
                profile, window = profile_for_request(IntentRequest(input=query), today=TODAY)
                self.assertEqual(profile, expected)
                self.assertTrue(WORKFLOW_PROFILES[profile] <= FIELDS.keys())
                for required in ('employees', 'departments', 'clients', 'projects', 'tasks', 'issues'):
                    self.assertIn(required, WORKFLOW_PROFILES[profile])
                self.assertEqual(window is not None, expected == 'usage')

    def test_followups_and_unrecognized_queries_use_full_snapshot(self):
        for query in ['Compare with previous period', 'Focus on blocked work', 'Show only the last 14 days']:
            request = IntentRequest(input=query, context_token='existing-context')
            self.assertEqual(profile_for_request(request), (None, None))
        self.assertEqual(profile_for_request(IntentRequest(input='Explain unfamiliar goal')), (None, None))

    def test_safe_switch_and_compound_queries_fall_back_to_full(self):
        with patch.dict('os.environ', {'KAIROS_INTELLIGENCE_FULL_SNAPSHOT': '1'}):
            self.assertEqual(profile_for_request(IntentRequest(input='Who owns task t1?')), (None, None))
        self.assertEqual(profile_for_request(IntentRequest(input='Prepare a meeting and investigate usage')), (None, None))

    def test_usage_window_includes_previous_comparison_period(self):
        profile, window = profile_for_request(IntentRequest(input='Investigate product usage for Northstar Retail'), today=date(2026,10,11))
        self.assertEqual((profile, window), ('usage', (date(2026,9,14), date(2026,10,11))))
        profile, window = profile_for_request(IntentRequest(input='Investigate last 7 days usage'), today=date(2026,10,11))
        self.assertEqual((profile, window), ('usage', (date(2026,9,28), date(2026,10,11))))
        self.assertEqual(profile_for_request(IntentRequest(input='Investigate yesterday usage'), today=date(2026,10,11)), (None,None))

    def test_profile_query_bounded_read_only_and_no_secrets(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [
            {'table_name': 'tasks', 'payload': {'id':'t1','title':'Validate SSO callback fix', 'status':'Blocked','owner_employee_id':'e1'}}
        ]
        @contextmanager
        def read(_user, *, timings=None):
            if timings is not None:
                timings.update(db_pool_ms=4.2, db_setup_ms=9.5)
            yield connection
        with patch('backend.intelligence.repository.read_connection', read):
            data = load_snapshot(USER, profile='usage', usage_window=(date(2026,9,14), date(2026,10,11)))
        query, args = connection.execute.call_args.args
        sql_text = query.as_string()
        self.assertIn('UNION ALL', sql_text)
        self.assertIn('"product_usage"', sql_text)
        self.assertNotIn('"employee_schedule_blocks"', sql_text)
        self.assertIn('"date" >= %s AND "date" <= %s', sql_text)
        self.assertIn('LIMIT %s', sql_text)
        self.assertNotIn('employee_access', sql_text)
        self.assertNotIn('password', sql_text.lower())
        self.assertEqual(len(args), len(WORKFLOW_PROFILES['usage'])+2)
        self.assertEqual(data.get('tasks','t1')['status'],'Blocked')
        self.assertEqual(data.timings['db_pool_ms'],4.2)
        self.assertGreaterEqual(data.timings['db_sql_ms'],0)
        self.assertGreaterEqual(data.timings['db_fetch_ms'],0)
        self.assertGreaterEqual(data.timings['db_decode_ms'],0)

    def test_profiles_do_not_change_supported_six_workflow_plans_on_fixture(self):
        baseline, knowledge = fixture(), Knowledge()
        for prompt, profile in self.CASES:
            with self.subTest(prompt=prompt):
                optimized = Snapshot({table: baseline.rows(table) for table in WORKFLOW_PROFILES[profile]})
                original_intent=resolve_intent(IntentRequest(input=prompt), baseline, USER, today=TODAY)
                optimized_intent=resolve_intent(IntentRequest(input=prompt), optimized, USER, today=TODAY)
                self.assertEqual(original_intent.model_dump(),optimized_intent.model_dump())
                full_plan=compose_workspace(baseline, knowledge, original_intent, today=TODAY)
                thin_plan=compose_workspace(optimized, knowledge, optimized_intent, today=TODAY)
                self.assertEqual([c.type for c in full_plan.components],[c.type for c in thin_plan.components])
                self.assertEqual([c.text for c in full_plan.claims], [c.text for c in thin_plan.claims])
                for dataset in ('clients', 'projects', 'tasks', 'issues', 'meetings', 'usage', 'usage_metrics', 'capacity', 'contracts'):
                    self.assertEqual(full_plan.datasets.get(dataset), thin_plan.datasets.get(dataset), dataset)
                Workspace.model_validate(thin_plan.model_dump())

    def test_v2_schema_and_timing_header_unchanged(self):
        snapshot_data=fixture()
        snapshot_data.load_ms=101.0
        snapshot_data.timings={'db_pool_ms':1.2,'db_setup_ms':2.3,'db_sql_ms':80.,'db_fetch_ms':10.,'db_decode_ms':1.}
        app.dependency_overrides[current_user]=lambda: USER
        app.dependency_overrides[plan_snapshot]=lambda: snapshot_data
        try:
            response=TestClient(app).post('/api/intelligence/workspace/plan',json={'input':'Who owns task t1?'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['schemaVersion'],2)
            self.assertIn('datasets',response.json())
            for stage in ('snapshot','db_pool_ms','db_setup_ms','db_sql_ms','db_fetch_ms','db_decode_ms','intent','compose'):
                self.assertIn(stage+';dur=',response.headers['server-timing'])
            self.assertNotIn('Bearer',response.headers['server-timing'])
        finally:
            app.dependency_overrides.clear()

if __name__=='__main__':
    unittest.main()
