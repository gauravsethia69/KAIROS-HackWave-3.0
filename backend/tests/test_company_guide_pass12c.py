"""Offline tests: no live DB, Groq credentials, or external network calls."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from backend.intelligence.company_guide import prepare_guide, enrich_guide, _validate_summary, GuideSummary, is_onboarding
from backend.intelligence.groq_focus import _recent, _usage


class CompanyGuidePass12CTests(unittest.TestCase):
    def setUp(self):
        _usage.update(day=None, requests=0, estimated_tokens=0)
        _recent.clear()

    def test_onboarding_uses_exact_recorded_atlas_pages_and_statuses(self):
        self.assertTrue(is_onboarding('I am a new employee how do things work'))
        guide = prepare_guide('I am a new employee how do things work')
        self.assertEqual(guide['status'], 'ready')
        self.assertEqual([p['page'] for p in guide['passages']], [1, 2, 3, 4, 5])
        self.assertEqual(guide['passages'][3]['status'], 'proposed')
        self.assertIn('proposed', guide['passages'][3]['citation'])
        self.assertIn('PostgreSQL', guide['authority'])

    def test_general_question_is_retrieved_without_adding_db_facts(self):
        guide = prepare_guide('What is Soryu Guard identity and SSO?')
        self.assertEqual(guide['passages'][0]['source_id'], 'product-guard')
        self.assertEqual(guide['passages'][0]['page'], 16)

    def test_gibberish_has_no_invented_answer(self):
        guide = prepare_guide('zzzxxyyq qwerty987654')
        self.assertEqual(guide['status'], 'not_found')
        self.assertEqual(guide['passages'], [])

    def test_no_groq_if_disabled(self):
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED': 'false', 'GROQ_API_KEY':'unused'}), \
             patch('backend.intelligence.company_guide.httpx.Client', side_effect=AssertionError('network used')):
            self.assertEqual(enrich_guide('I am a new employee how do things work')['status'], 'off')

    def test_groq_emits_cited_summaries_only_from_sent_passages(self):
        guide = prepare_guide('I am a new employee how do things work')
        ids = [p['id'] for p in guide['passages']]
        response = GuideSummary.model_validate({'items': [
            {'chunk_id': ids[0], 'summary': 'SORYU has four recorded products described in the company reference.'},
            {'chunk_id': ids[3], 'summary': 'A proposed model describes how departments collaborate; it is not approved policy.'},
        ]})
        result = _validate_summary(response, guide['passages'])
        self.assertEqual(result[1]['status'], 'proposed')
        self.assertEqual(result[1]['page'], 4)
        self.assertEqual(result[0]['chunk_id'], ids[0])
        with self.assertRaises(ValueError):
            _validate_summary(GuideSummary.model_validate({'items': [
                {'chunk_id': 'invented-id', 'summary': 'Invented employee policy from nowhere.'},
                {'chunk_id': ids[0], 'summary': 'Another invented employee policy is not allowed.'},
            ]}), guide['passages'])

    def test_unauthorized_repeated_id_and_policy_claims_rejected(self):
        guide = prepare_guide('I am a new employee how do things work')
        ident = guide['passages'][0]['id']
        with self.assertRaises(ValueError):
            _validate_summary(GuideSummary.model_validate({'items': [
                {'chunk_id': ident, 'summary': 'One company reference guides the user.'},
                {'chunk_id': ident, 'summary': 'A second company reference repeats the first.'},
            ]}), guide['passages'])
        with self.assertRaises(ValueError):
            _validate_summary(GuideSummary.model_validate({'items': [
                {'chunk_id': ident, 'summary': 'This is mandatory company policy for everyone.'},
                {'chunk_id': guide['passages'][1]['id'], 'summary': 'The company records employees by department.'},
            ]}), guide['passages'])

    def test_mocked_api_success_uses_bounded_context_and_shared_budget(self):
        sources = prepare_guide('I am a new employee how do things work')['passages']
        mocked = MagicMock()
        provider = mocked.return_value.__enter__.return_value.post.return_value
        provider.content = b'{"valid":true}'
        provider.json.return_value = {'choices': [{'message': {'content': json.dumps({'items': [
            {'chunk_id': sources[1]['id'], 'summary': 'The organization records departments and manager links.'},
            {'chunk_id': sources[3]['id'], 'summary': 'The cross-department collaboration model is proposed, not approved.'},
        ]})}}]}
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'private-test-key'}), \
             patch('backend.intelligence.company_guide.httpx.Client', mocked):
            result = enrich_guide('I am a new employee how do things work')
        self.assertEqual(result['status'], 'enriched')
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(_usage['requests'], 1)
        call = mocked.return_value.__enter__.return_value.post.call_args
        data = json.dumps(call.kwargs['json'])
        self.assertNotIn('database_url', data.lower())
        self.assertNotIn('employee_access', data)
        self.assertLess(len(data), 7000)
        self.assertNotIn('private-test-key', data)
        self.assertIn('atlas-', data)
        self.assertEqual(call.args[0], 'https://api.groq.com/openai/v1/chat/completions')

    def test_provider_exception_uses_references_without_leak(self):
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'private-test-key'}), \
             patch('backend.intelligence.company_guide.httpx.Client', side_effect=ValueError('secret accidental error')):
            self.assertEqual(enrich_guide('I am a new employee how do things work'), {'status': 'fallback', 'items': []})

    def test_budget_zero_falls_back_without_network(self):
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'secret', 'KAIROS_GROQ_DAILY_CALL_LIMIT':'0'}), \
             patch('backend.intelligence.company_guide.httpx.Client', side_effect=AssertionError('should not call')):
            self.assertEqual(enrich_guide('I am a new employee how do things work')['status'], 'budget')


class GuideRouteTests(unittest.TestCase):
    def test_both_routes_require_existing_employee_auth(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.company_guide import router
        app=FastAPI();app.include_router(router)
        with TestClient(app) as client:
            for p in ('sources', 'explain'):
                response=client.post('/api/intelligence/company-guide/'+p, json={'input':'I am a new employee'})
                self.assertEqual(response.status_code, 401)

    def test_sources_are_fast_and_db_independent_and_bounded(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.company_guide import router
        from backend.auth import current_user
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[current_user] = lambda: object()
        with TestClient(app) as client:
            result=client.post('/api/intelligence/company-guide/sources',json={'input':'I am a new employee how do things work'})
            too_long=client.post('/api/intelligence/company-guide/sources',json={'input':'x'*700})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers.get('cache-control'), 'private, no-store')
        self.assertEqual(result.json()['passages'][3]['page'], 4)
        self.assertEqual(too_long.status_code, 422)

if __name__=='__main__':
    unittest.main()
