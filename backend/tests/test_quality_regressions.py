"""Backend-only quality and performance regressions, no cloud calls."""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from backend.auth import current_user
from backend.main import app
from backend.routers.intelligence import snapshot, plan_snapshot
from backend.intelligence.catalog import FIELDS
from backend.intelligence.intent import resolve_intent
from backend.intelligence.knowledge import Knowledge
from backend.intelligence.models import IntentRequest, Workspace
from backend.intelligence.repository import Snapshot, load_snapshot
from backend.intelligence.workspace import compose_workspace
from backend.tests.intelligence_fixtures import fixture, USER, TODAY


class QualityRegressions(unittest.TestCase):
    def setUp(self):
        self.data, self.knowledge = fixture(), Knowledge()

    def ask(self, prompt):
        intent = resolve_intent(IntentRequest(input=prompt), self.data, USER, today=TODAY)
        return compose_workspace(self.data, self.knowledge, intent, today=TODAY)

    def test_simple_task_ownership_direct_answer_no_generic_delay_warning(self):
        plan = self.ask('Who owns task t1?')
        self.assertEqual(plan.intent.entities[-1].entity_type, 'task')
        self.assertEqual(plan.status, 'ready')
        self.assertEqual([c.props.selector for c in plan.components], ['insights', 'tasks'])
        observations = [c.text for c in plan.claims if c.kind == 'observation']
        self.assertEqual(len(observations), 1)
        self.assertIn('Avery Test', observations[0])
        self.assertFalse(any('causal explanation for delay' in c.text for c in plan.claims))
        self.assertFalse(any(c.kind == 'proposed_action' for c in plan.claims))
        self.assertFalse(any(c.props.selector in ('issues','projects') for c in plan.components))
        Workspace.model_validate(plan.model_dump())

    def test_explicit_project_owner_excludes_client_account_manager(self):
        project = self.data.get('projects','p1')
        self.assertEqual(project['owner_employee_id'], 'e1')
        plan = self.ask('Who owns project p1?')
        claims = [c.text for c in plan.claims if c.kind == 'observation']
        self.assertEqual(len(claims), 1)
        self.assertIn('Avery Test', claims[0])
        self.assertNotIn('Riley Fixture', claims[0])
        self.assertEqual([c.props.selector for c in plan.components], ['insights','projects'])

    def test_blocked_task_with_no_dependency_does_not_invent_one(self):
        tables = {table: [dict(row) for row in rows] for table,rows in self.data.tables.items()}
        tables['tasks'][0]['blocker_task_id'] = None
        self.data = Snapshot(tables)
        plan = self.ask('Who owns the blocked SSO task?')
        self.assertIn('specific blocking-task dependency is recorded', ' '.join(c.text for c in plan.claims))
        self.assertFalse(plan.datasets['responsibilities'][0]['blocker_chain'])
        self.assertTrue(all(c.evidence_ids for c in plan.claims if c.kind == 'observation'))

    def test_six_supported_workflows_keep_distinct_data_bound_widgets(self):
        scenarios = [
            ('Prepare for tomorrow\'s OrbitPay client meeting', 'client_meeting_prep'),
            ('Investigate declining product usage', 'product_usage_investigation'),
            ("Why is Atlas Media Group's reporting project delayed?", 'project_delivery_review'),
            ('Summarize urgent support incidents', 'support_incident_command'),
            ('Show Engineering workload', 'team_workload_planning'),
            ('Prepare a leadership briefing', 'executive_briefing'),
        ]
        signatures=[]
        for query, expected in scenarios:
            with self.subTest(query=query):
                plan=self.ask(query)
                self.assertEqual(plan.intent.name,expected)
                self.assertNotEqual(plan.status,'unsupported')
                self.assertTrue(plan.components)
                self.assertTrue(plan.evidence)
                self.assertEqual(plan.source,'deterministic-enterprise')
                Workspace.model_validate(plan.model_dump())
                signatures.append(tuple(c.type for c in plan.components))
        self.assertEqual(len(set(signatures)),6)

    def test_database_snapshot_one_readonly_batched_query_and_bounds(self):
        connection=MagicMock()
        connection.execute.return_value.fetchall.return_value=[
            {'table_name':'tasks','payload':{'id':'t1','title':'Validate SSO callback fix','status':'Blocked','owner_employee_id':'e1'}}
        ]
        @contextmanager
        def read(_, *, timings=None):
            yield connection
        with patch('backend.intelligence.repository.read_connection',read):
            data=load_snapshot(USER)
        self.assertEqual(len(connection.execute.call_args_list),1)
        sql_text=connection.execute.call_args.args[0].as_string()
        params=connection.execute.call_args.args[1]
        self.assertEqual(len(params),len(FIELDS))
        self.assertEqual(params[list(FIELDS).index('product_usage')],2001)
        self.assertIn('UNION ALL',sql_text)
        self.assertIn('LIMIT %s',sql_text)
        self.assertNotIn('employee_access',sql_text)
        self.assertNotIn('"email"',sql_text)
        self.assertEqual(data.get('tasks','t1')['status'],'Blocked')
        self.assertGreaterEqual(data.load_ms,0)

    def test_api_reports_per_stage_timing_without_sensitive_data(self):
        app.dependency_overrides[current_user]=lambda: USER
        app.dependency_overrides[snapshot]=lambda: self.data
        app.dependency_overrides[plan_snapshot]=lambda: self.data
        try:
            client=TestClient(app)
            result=client.post('/api/intelligence/workspace/plan',json={'input':'Who owns task t1?'})
            self.assertEqual(result.status_code,200,result.text)
            header=result.headers.get('server-timing','')
            self.assertIn('snapshot;dur=',header)
            self.assertIn('intent;dur=',header)
            self.assertIn('compose;dur=',header)
            self.assertNotIn('t1',header)
        finally:
            app.dependency_overrides.clear()

if __name__ == '__main__':
    unittest.main()
