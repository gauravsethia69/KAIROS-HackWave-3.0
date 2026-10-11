"""Pass 12E offline regression: verify route isolation, auth, budgets and caching."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from backend.intelligence.general_advice import is_general_advice, _extract_advice, advise
from backend.intelligence.groq_focus import _usage, _recent
from backend.auth import Identity, current_user


PROMPT = 'How to increase sales?'


class AdviceTests(unittest.TestCase):
    def setUp(self):
        _usage.update(day=None, requests=0, estimated_tokens=0)
        _recent.clear()

    def test_broad_advice_routes(self):
        for question in ['How to increase sales?', 'How can we increase sales?', 'What can we do to increase sales?',
                         'How can I improve productivity?', 'How do we improve customer retention?',
                         'How to make meetings effective?', 'What are some ways to improve team collaboration?']:
            with self.subTest(question=question):
                self.assertTrue(is_general_advice(question))

    def test_database_legal_user_actions_not_intercepted(self):
        for question in ['Show Engineering workload', 'Show our sales metrics',
                         'Review delayed projects for Atlas Media Group',
                         'How can we increase sales for OrbitPay?',
                         'Why did our sales drop last month?', 'How to schedule a meeting?',
                         'I am a new employee, how do things work?',
                         'How to increase sales based on our actual recorded metrics?',
                         'How to update customer accounts?']:
            with self.subTest(question=question):
                self.assertFalse(is_general_advice(question))

    def test_question_length_and_bad_output(self):
        self.assertFalse(is_general_advice('a'*800))
        with self.assertRaises(ValueError):
            _extract_advice('{"notsteps":true}')
        with self.assertRaises(ValueError):
            _extract_advice(json.dumps({'title':'Title','introduction':'Intro','caution':'Note',
                                         'steps':[{'action':'', 'why':''}]}))
        with self.assertRaises(ValueError):
            _extract_advice(json.dumps({'title':'Title','introduction':'Intro','caution':'Note',
                                         'steps':[{'action':'Use https://example.com', 'why':'Check'}]}))

    def test_short_valid_ai_advice_is_accepted(self):
        result = _extract_advice(json.dumps({'title':'Grow sales','introduction':'Try a focused approach.',
                'steps':[{'action':'Clarify target audience', 'why':'Different buyers have different needs.'}],
                'caution':'Test before scaling.'}))
        self.assertEqual(result['steps'][0]['action'], 'Clarify target audience')

    def test_disabled_never_calls_groq(self):
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'false','GROQ_API_KEY':'testkey'}), \
             patch('backend.intelligence.general_advice.httpx.Client',side_effect=AssertionError('network')):
            self.assertEqual(advise(PROMPT,'person')['status'],'off')

    def test_operational_question_never_calls_groq(self):
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'testkey'}), \
             patch('backend.intelligence.general_advice.httpx.Client',side_effect=AssertionError('network')):
            self.assertEqual(advise('Show our sales records','person')['status'],'not_general')

    def test_budget_exceeded_never_calls_groq(self):
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'testkey'}), \
             patch('backend.intelligence.general_advice._budget_allows',return_value=False), \
             patch('backend.intelligence.general_advice.httpx.Client',side_effect=AssertionError('network')):
            self.assertEqual(advise(PROMPT,'viewer-1')['status'],'budget')

    def test_mock_groq_one_call_then_identity_scoped_cache(self):
        mock_client = MagicMock()
        reply = mock_client.return_value.__enter__.return_value.post.return_value
        reply.content = b'{"mock":true}'
        reply.json.return_value = {'choices':[{'message': {'content': json.dumps({
            'title':'Practical ways to grow sales',
            'introduction':'Prioritize a measurable experiment rather than guessing.',
            'steps':[{'action':'Interview potential customers', 'why':'Understand purchasing barriers.'},
                     {'action':'Measure conversion', 'why':'Learn which opportunities improve.'}],
            'caution':'These are general ideas, not verified business performance.'})}}],
            'usage': {'prompt_tokens':80,'completion_tokens':110}}
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'fake-unit-test'}), \
             patch('backend.intelligence.general_advice._budget_allows',return_value=True), \
             patch('backend.intelligence.general_advice.httpx.Client',mock_client):
            result = advise(PROMPT,'viewer-a:employee')
            cached = advise(PROMPT,'viewer-a:employee')
            another = advise(PROMPT,'viewer-b:employee')
        self.assertEqual(result['status'],'enriched')
        self.assertTrue(cached['cached'])
        self.assertFalse(another['cached'])
        self.assertEqual(mock_client.return_value.__enter__.return_value.post.call_count,2)
        kwargs = mock_client.return_value.__enter__.return_value.post.call_args.kwargs
        self.assertLess(len(json.dumps(kwargs['json'])),4500)
        self.assertNotIn('fake-unit-test',json.dumps(kwargs['json']))
        self.assertIn('How to increase sales?',json.dumps(kwargs['json']))
        self.assertNotIn('employee_id',json.dumps(kwargs['json']))

    def test_http_error_returns_fallback_no_data_leaks(self):
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'unit-test'}), \
             patch('backend.intelligence.general_advice._budget_allows',return_value=True), \
             patch('backend.intelligence.general_advice.httpx.Client',side_effect=ValueError('private-data')):
            self.assertEqual(advise(PROMPT,'failure-viewer'),{'status':'fallback','advice':None})

    def test_auth_route_and_query_contract(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.general_advice import router
        app = FastAPI(); app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/intelligence/general-advice/answer',json={'input':PROMPT}).status_code,401)
        app.dependency_overrides[current_user] = lambda: Identity(
            id=UUID('11111111-1111-4111-8111-111111111111'), employee_id='emp001', access_role='employee')
        with patch('backend.routers.general_advice.advise', return_value={'status':'off','advice':None}) as fn:
            with TestClient(app) as client:
                response = client.post('/api/intelligence/general-advice/answer',json={'input':PROMPT})
                bad = client.post('/api/intelligence/general-advice/answer',json={'input':PROMPT,'verified_metrics':[42]})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers.get('cache-control'),'private, no-store')
            self.assertEqual(bad.status_code,422)
            self.assertEqual(fn.call_args.kwargs['viewer'],'11111111-1111-4111-8111-111111111111:emp001:employee')

if __name__ == '__main__': unittest.main()
