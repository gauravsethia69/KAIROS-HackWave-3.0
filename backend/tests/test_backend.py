import json
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.auth import Identity, current_user
from backend.main import app
from backend.schemas import WorkspacePlan
from backend.services.planner import compose, local_plan
from backend.services import repository

USER = Identity(id=UUID('11111111-1111-4111-8111-111111111111'), employee_id='fixture-employee', access_role='employee')


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def authorized(self):
        app.dependency_overrides[current_user] = lambda: USER

    def test_health(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'kairos-api'})

    def test_protected_routes_reject_missing_bearer(self):
        for route in ['/api/clients', '/api/clients/acme', '/api/clients/acme/meetings', '/api/clients/acme/usage', '/api/projects', '/api/tasks', '/api/communications', '/api/issues', '/api/workspace/sessions']:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 401)
        self.assertEqual(self.client.post('/api/workspace/plan', json={'input': 'test', 'previous': compose().model_dump(exclude_none=True)}).status_code, 401)

    def test_invalid_and_expired_bearer_are_verified_remotely(self):
        for token in ['invalid', 'expired']:
            fake = AsyncMock()
            fake.get.return_value = httpx.Response(401)
            with patch('backend.auth.settings', SimpleNamespace(supabase_url='https://morph-ai.example', supabase_key='public-key')), patch('backend.auth.httpx.AsyncClient') as cls:
                cls.return_value.__aenter__.return_value = fake
                self.assertEqual(self.client.get('/api/clients', headers={'Authorization': f'Bearer {token}'}).status_code, 401)
                self.assertEqual(fake.get.call_args.kwargs['headers']['Authorization'], f'Bearer {token}')

    def test_verified_identity_reaches_repository(self):
        fake = AsyncMock()
        fake.get.return_value = httpx.Response(200, json={'id': str(USER.id)})
        with patch('backend.auth.settings', SimpleNamespace(supabase_url='https://morph-ai.example', supabase_key='public')), patch('backend.auth.httpx.AsyncClient') as cls, patch('backend.database.lookup_active_employee', return_value={'employee_id': USER.employee_id, 'access_role': USER.access_role}), patch('backend.routers.api.repository.sessions', return_value=[]) as sessions:
            cls.return_value.__aenter__.return_value = fake
            response = self.client.get('/api/workspace/sessions', headers={'Authorization': 'Bearer verified-by-supabase'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(sessions.call_args.args[0].id, USER.id)

    def test_session_owner_cannot_be_supplied_by_request(self):
        self.authorized()
        response = self.client.post('/api/workspace/sessions', json={'plan': compose().model_dump(exclude_none=True), 'user_id': 'someone-else'})
        self.assertEqual(response.status_code, 422)

    def test_repository_scopes_reads_and_inserts(self):
        connection = MagicMock()
        @contextmanager
        def fake_connection(user):
            self.assertEqual(user.id, USER.id)
            yield connection
        with patch('backend.services.repository.user_connection', fake_connection):
            repository.sessions(USER)
            query, parameters = connection.execute.call_args.args
            self.assertIn('WHERE user_id = %s', query)
            self.assertEqual(parameters, (USER.id,))
            repository.save(compose(), USER)
            self.assertEqual(connection.execute.call_args.args[1][0], USER.id)

    def test_database_sets_transaction_local_restricted_role_and_claims(self):
        from backend.database import user_connection
        connection = MagicMock()
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = connection
        with patch('backend.database.get_pool', return_value=pool):
            with user_connection(USER):
                pass
        calls = connection.execute.call_args_list
        self.assertEqual(calls[0].args[0], 'SET LOCAL ROLE authenticated')
        self.assertIn(str(USER.id), calls[1].args[1])
        self.assertEqual(json.loads(calls[2].args[1][0])['role'], 'authenticated')

    def test_three_scenarios_and_contract_export(self):
        self.authorized()
        plans = []
        for text, intent, top in [
            ("Prepare me for tomorrow's client meeting with Acme Corp.", 'meeting', 'MeetingBrief'),
            ("Investigate Acme Corp's declining product usage.", 'usage', 'UsageChart'),
            ('Review projects falling behind schedule.', 'projects', 'ProjectProgress'),
        ]:
            response = self.client.post('/api/workspace/plan', json={'input': text, 'previous': compose().model_dump(exclude_none=True)})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result['source'], 'deterministic')
            self.assertEqual(result['plan']['intent'], intent)
            self.assertEqual(result['plan']['layout'][0]['type'], top)
            self.assertNotIn('clarification', result['plan'])
            plans.append(result['plan'])
        # Consumed by the frontend Zod test for cross-language contract verification.
        output = Path('artifacts/backend-plans.json')
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(plans), encoding='utf-8')

    def test_context_followups(self):
        plan = local_plan('Investigate Acme usage', compose())
        for text in ['Show only the last 14 days', 'Compare this with the previous period', 'Move the usage chart to the top', 'Show this information as a table instead', 'Focus on unresolved issues']:
            plan = local_plan(text, plan)
            self.assertEqual(plan.selectedEntityIds, ['acme'])
        self.assertEqual(plan.filters.days, 14)
        self.assertTrue(plan.filters.compare)
        self.assertTrue(plan.filters.unresolvedOnly)
        self.assertEqual(plan.layout[0].selector, 'issues')
        self.assertIn('DataTable', [w.type for w in plan.layout])

    def test_ambiguity(self):
        plan = local_plan('Prepare for a client meeting', compose())
        self.assertIsNotNone(plan.clarification)
        self.assertEqual(local_plan('Nova', plan).selectedEntityIds, ['nova'])

    def test_invalid_schemas_rejected(self):
        for field, bad in [('type', 'ExecuteSQL'), ('selector', 'auth.users'), ('selector', 'usage')]:
            data = compose().model_dump(exclude_none=True)
            data['layout'][0][field] = bad
            with self.assertRaises(ValidationError):
                WorkspacePlan.model_validate(data)

    def test_ai_unconfigured_falls_back(self):
        self.authorized()
        with patch('backend.services.ai.settings', SimpleNamespace(ai_key='', ai_base_url='', ai_model='')):
            response = self.client.post('/api/workspace/plan', json={'input': 'Investigate Acme usage', 'previous': compose().model_dump(exclude_none=True), 'use_ai': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['source'], 'fallback')

    def test_ai_failure_falls_back_without_leaking_errors(self):
        self.authorized()
        with patch('backend.services.ai.settings', SimpleNamespace(ai_key='secret', ai_base_url='https://ai.example/v1', ai_model='model')), patch('backend.services.ai.claim_ai_request', return_value=True), patch('backend.services.ai.httpx.AsyncClient', side_effect=httpx.ConnectError('private details')):
            response = self.client.post('/api/workspace/plan', json={'input': 'Investigate Acme usage', 'previous': compose().model_dump(exclude_none=True), 'use_ai': True})
        self.assertEqual(response.json()['source'], 'fallback')
        self.assertNotIn('private details', response.text)

    def test_unknown_client_is_not_found(self):
        self.authorized()
        with patch('backend.services.repository.records', return_value=[]):
            self.assertEqual(self.client.get('/api/clients/unknown').status_code, 404)

    def test_provider_output_is_validated_and_labeled(self):
        self.authorized()
        real_client = httpx.AsyncClient
        for invalid in (False, True):
            plan = compose('usage', ['acme']).model_dump(exclude_none=True)
            if invalid:
                plan['layout'][0]['selector'] = 'auth.users'
            transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(plan)}}]}))
            with patch('backend.services.ai.settings', SimpleNamespace(ai_key='secret', ai_base_url='https://ai.example/v1', ai_model='model')), patch('backend.services.ai.claim_ai_request', return_value=True), patch('backend.services.ai.httpx.AsyncClient', side_effect=lambda **kwargs: real_client(transport=transport, **kwargs)):
                response = self.client.post('/api/workspace/plan', json={'input': 'Investigate Acme usage', 'previous': compose().model_dump(exclude_none=True), 'use_ai': True})
            self.assertEqual(response.status_code, 200)
            # Active routes now prohibit external AI even when a provider is configured.
            self.assertEqual(response.json()['source'], 'fallback')

    def test_body_limit_and_cors(self):
        self.assertEqual(self.client.post('/api/workspace/plan', content=b'x' * 24001).status_code, 413)
        for origin, allowed in [('http://localhost:5173', True), ('https://untrusted.example', False)]:
            response = self.client.options('/api/clients', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET'})
            self.assertEqual('access-control-allow-origin' in response.headers, allowed)


if __name__ == '__main__':
    unittest.main()
