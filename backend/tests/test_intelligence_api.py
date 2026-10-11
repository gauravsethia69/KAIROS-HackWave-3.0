import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from psycopg import OperationalError

from backend.auth import current_user
from backend.database import lookup_active_employee, user_connection
from backend.main import app
from backend.routers.intelligence import snapshot, plan_snapshot
from backend.intelligence.models import Workspace
from backend.intelligence.repository import load_snapshot
from backend.tests.intelligence_fixtures import fixture, USER, OTHER


class IntelligenceAPITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.data = fixture()

    def tearDown(self):
        app.dependency_overrides.clear()

    def authorized(self, user=USER):
        app.dependency_overrides[current_user] = lambda: user
        app.dependency_overrides[snapshot] = lambda: self.data
        app.dependency_overrides[plan_snapshot] = lambda: self.data

    def test_all_enterprise_endpoints_require_authentication(self):
        for route in ['/api/intelligence/knowledge/search?q=SSO', '/api/intelligence/knowledge/documents/product-guard', '/api/intelligence/employees/me', '/api/intelligence/employees/search?q=Avery', '/api/intelligence/entities/task/t1', '/api/intelligence/responsibility/task/t1', '/api/intelligence/evidence/db:tasks:t1:status']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 401)
        for route in ['/api/intelligence/intent/resolve', '/api/intelligence/workspace/plan']:
            self.assertEqual(self.client.post(route, json={'input': 'Review my tasks'}).status_code, 401)

    def test_invalid_token_unlinked_and_disabled_membership(self):
        for status, membership, expected in [(401, None, 401), (200, None, 403), (200, None, 403)]:
            fake = AsyncMock()
            fake.get.return_value = httpx.Response(status, json={'id': str(USER.id)})
            with patch('backend.auth.settings', SimpleNamespace(supabase_url='https://auth.example', supabase_key='test-public')), patch('backend.auth.httpx.AsyncClient') as cls, patch('backend.database.lookup_active_employee', return_value=membership) as lookup:
                cls.return_value.__aenter__.return_value = fake
                response = self.client.get('/api/intelligence/knowledge/documents/product-guard', headers={'Authorization': 'Bearer test-token'})
                self.assertEqual(response.status_code, expected)
                if status == 401:
                    lookup.assert_not_called()

    def test_membership_query_requires_enabled_and_verified_uuid(self):
        connection, pool = MagicMock(), MagicMock()
        pool.connection.return_value.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = None
        with patch('backend.database.get_pool', return_value=pool):
            self.assertIsNone(lookup_active_employee(USER.id))
        query, parameters = connection.execute.call_args.args
        self.assertIn('account_enabled IS TRUE', query)
        self.assertIn('auth_user_id = %s', query)
        self.assertEqual(parameters, (USER.id,))

    def test_auth_me_unchanged_and_uses_verified_membership(self):
        self.authorized()
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.json(), {'user_id': str(USER.id), 'employee_id': USER.employee_id, 'access_role': USER.access_role})

    def test_server_identity_not_browser_identity(self):
        self.authorized()
        for field in ('employee_id', 'auth_user_id', 'department', 'role'):
            response = self.client.post('/api/intelligence/workspace/plan', json={'input': 'Review my tasks', field: 'e3'})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get('/api/intelligence/employees/me?employee_id=e3').json()['entity']['entity_id'], 'e1')

    def test_plans_and_navigation_resolve_without_llm(self):
        self.authorized()
        examples = ['Who owns the blocked SSO task?', "Why is Atlas Media Group's reporting project delayed?", 'Prepare for an OrbitPay client meeting.', 'Show Engineering team workload.', 'Investigate declining product usage.', 'Summarize urgent support incidents.']
        with patch('backend.services.ai.httpx.AsyncClient', side_effect=AssertionError('LLM/network not permitted')):
            for example in examples:
                with self.subTest(example=example):
                    response = self.client.post('/api/intelligence/workspace/plan', json={'input': example})
                    self.assertEqual(response.status_code, 200, response.text)
                    plan = Workspace.model_validate(response.json())
                    self.assertTrue(plan.components)
                    self.assertEqual(plan.source, 'deterministic-enterprise')
                    for evidence in plan.evidence[:3]:
                        self.assertEqual(self.client.get(f'/api/intelligence/evidence/{evidence.id}').status_code, 200)

    def test_context_token_bound_to_current_employee(self):
        self.authorized()
        first = self.client.post('/api/intelligence/intent/resolve', json={'input': 'Review my tasks'}).json()
        self.authorized(OTHER)
        response = self.client.post('/api/intelligence/workspace/plan', json={'input': 'Show blocked work', 'context_token': first['context_token']})
        self.assertEqual(response.status_code, 404)

    def test_missing_invalid_and_unavailable_errors(self):
        self.authorized()
        self.assertEqual(self.client.get('/api/intelligence/knowledge/documents/missing').status_code, 404)
        self.assertEqual(self.client.get('/api/intelligence/entities/task/missing').status_code, 404)
        self.assertEqual(self.client.get('/api/intelligence/entities/task/bad!').status_code, 422)
        self.assertEqual(self.client.get('/api/intelligence/evidence/db:employee_access:e1:role').status_code, 400)
        self.assertEqual(self.client.get('/api/intelligence/knowledge/search?q=SSO&limit=999').status_code, 422)
        def unavailable():
            raise HTTPException(503, 'PostgreSQL operation unavailable')
        app.dependency_overrides[snapshot] = unavailable
        app.dependency_overrides[plan_snapshot] = unavailable
        self.assertEqual(self.client.post('/api/intelligence/workspace/plan', json={'input': 'Review tasks'}).status_code, 503)

    def test_readonly_scope_precedes_claim_queries(self):
        connection, pool = MagicMock(), MagicMock()
        pool.connection.return_value.__enter__.return_value = connection
        with patch('backend.database.get_pool', return_value=pool):
            with user_connection(USER, read_only=True):
                pass
        self.assertEqual(connection.execute.call_args_list[0].args[0], 'SET TRANSACTION READ ONLY')
        self.assertEqual(connection.execute.call_args_list[1].args[0], 'SET LOCAL ROLE authenticated')

    def test_db_errors_do_not_leak_connection_material(self):
        pool = MagicMock()
        pool.connection.side_effect = OperationalError('password=never-expose host=private')
        with patch('backend.database.get_pool', return_value=pool), self.assertRaises(HTTPException) as failure:
            with user_connection(USER, read_only=True):
                pass
        self.assertEqual(failure.exception.status_code, 503)
        self.assertNotIn('password', failure.exception.detail)

    def test_snapshot_queries_are_allowlisted_bounded_and_readonly(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []
        @contextmanager
        def read(_user, *, timings=None):
            yield connection
        with patch('backend.intelligence.repository.read_connection', read):
            load_snapshot(USER)
        for call in connection.execute.call_args_list:
            query, params = call.args
            text = query.as_string()
            self.assertTrue(text.startswith('SELECT '))
            self.assertIn('LIMIT %s', text)
            self.assertNotIn('employee_access', text)
            self.assertNotIn('"email"', text)
            self.assertNotIn('"metadata"', text)
            self.assertLessEqual(params[0], 2001)

    def test_legacy_planner_cannot_call_external_ai(self):
        from backend.services.planner import compose
        self.authorized()
        with patch('backend.services.ai.httpx.AsyncClient', side_effect=AssertionError('Forbidden')):
            response = self.client.post('/api/workspace/plan', json={'input': 'Investigate Acme usage', 'previous': compose().model_dump(exclude_none=True), 'use_ai': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['source'], 'fallback')
