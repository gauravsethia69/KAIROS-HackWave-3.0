"""Pass 12D: offline safety tests; no real provider or DB calls."""
from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from backend.intelligence.ai_usage import (cache_lookup, cache_success, record_attempt,
                                            record_completion, usage_snapshot)
from backend.intelligence.hybrid_explain import _facts, _accept, ExplanationResult, explain_verified_workspace
from backend.tests.test_groq_focus_pass12b import example_workspace
from backend.intelligence.groq_focus import _usage, _recent


class SelectiveAITests(unittest.TestCase):
    def setUp(self):
        _usage.update(day=None, requests=0, estimated_tokens=0)
        _recent.clear()

    def test_backend_workspace_skips_groq_by_default_even_when_enabled(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.auth import current_user, Identity
        from backend.routers.intelligence import router, plan_snapshot
        app = FastAPI(); app.include_router(router)
        identity = Identity(id=UUID('11111111-1111-4111-8111-111111111111'), employee_id='emp001', access_role='employee')
        app.dependency_overrides[current_user] = lambda: identity
        sentinel = MagicMock(load_ms=2, timings={}, cache_state='MISS')
        app.dependency_overrides[plan_snapshot] = lambda: sentinel
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'unit-test',
                                     'KAIROS_GROQ_RANK_OPERATIONS':'false'}), \
             patch('backend.routers.intelligence.resolve_intent', return_value=w.intent), \
             patch('backend.routers.intelligence.compose_workspace', return_value=w), \
             patch('backend.routers.intelligence.groq_enrich_with_deadline', side_effect=AssertionError('Groq ranking called')):
            with TestClient(app) as client:
                response=client.post('/api/intelligence/workspace/plan',json={'input':'Review delayed project'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['source'],'deterministic-enterprise')
        self.assertEqual(response.json()['intelligence']['status'],'off')
        self.assertEqual(response.headers['X-KAIROS-AI'],'off')
        self.assertEqual(_usage['requests'],0)

    def test_operational_ranking_explicit_opt_in_still_available(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.auth import current_user, Identity
        from backend.routers.intelligence import router, plan_snapshot
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[current_user]=lambda: Identity(id=UUID('11111111-1111-4111-8111-111111111111'), employee_id='emp001', access_role='employee')
        app.dependency_overrides[plan_snapshot]=lambda: MagicMock(load_ms=1,timings={},cache_state='HIT')
        w=example_workspace()
        with patch.dict(os.environ,{'KAIROS_GROQ_RANK_OPERATIONS':'true'}), \
             patch('backend.routers.intelligence.resolve_intent',return_value=w.intent), \
             patch('backend.routers.intelligence.compose_workspace',return_value=w), \
             patch('backend.routers.intelligence.groq_enrich_with_deadline',return_value=w) as model:
            with TestClient(app) as client:
                self.assertEqual(client.post('/api/intelligence/workspace/plan',json={'input':'show task'}).status_code,200)
        model.assert_called_once()

    def test_hybrid_context_contains_verified_claims_not_raw_datasets(self):
        w=example_workspace()
        facts=_facts(w)
        self.assertEqual(len(facts),2)
        self.assertEqual(facts[0]['sources'][0]['id'],'db:tasks:t1:status')
        self.assertNotIn('datasets',json.dumps(facts))
        self.assertNotIn('Root cause',json.dumps(facts))

    def test_forged_indices_rejected(self):
        facts=_facts(example_workspace())
        with self.assertRaises(ValueError):
            _accept(ExplanationResult.model_validate({'points':[{'claim_index':3,'explanation':'Unsupported cited story.'}]}),facts,[])
        with self.assertRaises(ValueError):
            _accept(ExplanationResult.model_validate({'points':[{'claim_index':0,'explanation':'A finding explained.'},
                      {'claim_index':0,'explanation':'Repeated claim summary.'}]}),facts,[])

    def test_on_demand_explanation_not_automatically_called_without_user_action(self):
        w=example_workspace()
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'false','GROQ_API_KEY':'placeholder'}), \
             patch('backend.intelligence.hybrid_explain.httpx.Client',side_effect=AssertionError('no network')):
            result=explain_verified_workspace('Explain task t1',w,'viewer-a')
        self.assertEqual(result['status'],'off')
        self.assertEqual(_usage['requests'],0)

    def test_model_response_has_trusted_evidence_and_limited_context(self):
        w=example_workspace(); mock=MagicMock()
        response=mock.return_value.__enter__.return_value.post.return_value
        response.content=b'{}'
        response.json.return_value={'choices':[{'message':{'content':json.dumps({'points':[
          {'claim_index':0,'explanation':'The supplied task record says it is blocked, but does not prove why.'}]})}}],
          'usage':{'prompt_tokens':310,'completion_tokens':90}}
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'private-unit-test'}), \
             patch('backend.intelligence.hybrid_explain.httpx.Client', mock):
            result=explain_verified_workspace('Explain task t1 blocked review',w,'viewer-a')
            cached=explain_verified_workspace('Explain task t1 blocked review',w,'viewer-a')
        self.assertEqual(result['status'],'enriched')
        self.assertEqual(result['points'][0]['evidence_ids'],['db:tasks:t1:status'])
        self.assertFalse(result['cached'])
        self.assertTrue(cached['cached'])
        self.assertEqual(mock.return_value.__enter__.return_value.post.call_count,1)
        sent=mock.return_value.__enter__.return_value.post.call_args.kwargs['json']
        self.assertNotIn('private-unit-test',json.dumps(sent))
        self.assertNotIn('\"datasets\":',json.dumps(sent))
        self.assertLess(len(json.dumps(sent)),6000)

    def test_cache_is_verified_identity_scoped(self):
        cache_success('company_guide','uuid-1:emp001:employee','digest',{'status':'enriched','items':[1]})
        self.assertIsNone(cache_lookup('company_guide','uuid-2:emp001:employee','digest'))
        self.assertIsNone(cache_lookup('company_guide','uuid-1:emp001:admin','digest'))
        self.assertEqual(cache_lookup('company_guide','uuid-1:emp001:employee','digest')['items'],[1])
        cache_lookup('company_guide','uuid-1:emp001:employee','digest')['items'].append('injected')
        self.assertEqual(cache_lookup('company_guide','uuid-1:emp001:employee','digest')['items'],[1])

    def test_usage_is_per_process_and_never_records_question_or_key(self):
        record_attempt('workspace_explanation', 'viewer-sample')
        record_completion('workspace_explanation',{'prompt_tokens':120,'completion_tokens':25,'prompt_tokens_details':{'cached_tokens':80}}, 'viewer-sample')
        out=usage_snapshot('viewer-sample'); row=out['by_feature']['workspace_explanation']
        self.assertGreaterEqual(row['input_tokens'],120)
        self.assertGreaterEqual(row['output_tokens'],25)
        self.assertEqual(out['scope'],'this_backend_process_only')
        self.assertNotIn('GROQ_API_KEY',str(out))

    def test_explain_route_requires_authentication(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.routers.intelligence import router
        app=FastAPI();app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/intelligence/workspace/explain',json={'input':'explain tasks'}).status_code,401)
            self.assertEqual(client.get('/api/intelligence/ai/usage').status_code,401)

    def test_explain_route_recomputes_source_under_verified_identity(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.auth import current_user, Identity
        from backend.routers.intelligence import router, plan_snapshot
        identity=Identity(id=UUID('11111111-1111-4111-8111-111111111111'),employee_id='emp001',access_role='employee')
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[current_user]=lambda:identity
        app.dependency_overrides[plan_snapshot]=lambda:MagicMock()
        w=example_workspace()
        with patch('backend.routers.intelligence.resolve_intent',return_value=w.intent), \
             patch('backend.routers.intelligence.compose_workspace',return_value=w) as compose, \
             patch('backend.routers.intelligence.explain_verified_workspace',return_value={'status':'off','points':[],'atlas_sources':[]}) as explain:
            with TestClient(app) as client:
                response=client.post('/api/intelligence/workspace/explain',json={'input':'Why is task t1 blocked?'})
                rejected=client.post('/api/intelligence/workspace/explain',json={'input':'x','claims':[{'text':'injection'}]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(rejected.status_code,422)
        compose.assert_called_once()
        self.assertIn('11111111-1111-4111-8111-111111111111',explain.call_args.kwargs['viewer'])

if __name__=='__main__':unittest.main()
