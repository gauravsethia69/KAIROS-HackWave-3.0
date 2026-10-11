"""Offline tests: no database, no Groq key, and no network required."""
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.intelligence.groq_focus import (_apply_choice, _input_payload, _recent,
                                             _usage, groq_enrich, GroqChoice)
from backend.intelligence.models import (BoundProps, Claim, ComponentPlan,
                                         EntityRef, Evidence, Navigation, ResolvedIntent, Workspace)


def example_workspace():
    evidence = [Evidence(
        id='db:tasks:t1:status', source_type='database', source_table='tasks',
        entity=EntityRef(entity_type='task', entity_id='t1'), document_id=None,
        title='Task t1', field='status', retrieved_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        navigation=Navigation(kind='entity_detail', entity=EntityRef(entity_type='task', entity_id='t1')),
    )]
    claims = [
        Claim(kind='observation', text='Task t1 is recorded as blocked.', evidence_ids=[evidence[0].id]),
        Claim(kind='calculation', text='One visible blocked task.', evidence_ids=[evidence[0].id]),
        Claim(kind='uncertainty', text='Root cause not established.'),
    ]
    components = [
        ComponentPlan(id='TaskList-tasks', type='TaskList', title='Tasks', priority=10,
                      order=0, size='wide', props=BoundProps(selector='tasks', record_ids=['t1']),
                      evidence_ids=[evidence[0].id], reason='Relevant task evidence'),
        ComponentPlan(id='InsightPanel-insights', type='InsightPanel', title='Evidence', priority=9,
                      order=1, size='medium', props=BoundProps(selector='insights', record_ids=['claim-0','claim-1','claim-2']),
                      evidence_ids=[evidence[0].id], reason='Grounded claims'),
    ]
    return Workspace(status='ready', title='Blocked work',
                     intent=ResolvedIntent(name='project_delivery_review', confidence=.82),
                     components=components,
                     datasets={'tasks': [{'id':'t1','status':'Blocked'}],
                               'insights': [{'id':f'claim-{i}', **claim.model_dump()} for i,claim in enumerate(claims)]},
                     evidence=evidence, claims=claims,
                     explanations=['Task evidence'], limitations=[], integration_requirements=[])


class GroqFocusSafetyTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {}, clear=False):
            _usage.update(day=None, requests=0, estimated_tokens=0)
            _recent.clear()

    def test_default_is_off_and_cannot_call_external_provider(self):
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'false', 'GROQ_API_KEY':'test'}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', side_effect=AssertionError('network used')):
            self.assertIs(groq_enrich('show blocked work', w), w)
            self.assertEqual(w.intelligence.status, 'off')

    def test_no_key_means_no_call(self):
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':''}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', side_effect=AssertionError('network used')):
            self.assertIs(groq_enrich('show blocked work', w), w)

    def test_only_reorders_allowlisted_components_and_existing_claims(self):
        w = example_workspace()
        result = _apply_choice(w, GroqChoice(component_ids=['InsightPanel-insights'], claim_indices=[1]))
        self.assertEqual(result.intelligence.status, 'enriched')
        self.assertEqual([c.id for c in result.components], ['InsightPanel-insights','TaskList-tasks'])
        self.assertEqual(result.claims[0].text, 'One visible blocked task.')
        self.assertEqual({x.text for x in result.claims}, {x.text for x in w.claims})
        self.assertEqual(result.datasets['tasks'], w.datasets['tasks'])
        self.assertEqual([x.id for x in result.evidence], [x.id for x in w.evidence])
        self.assertEqual([x['id'] for x in result.datasets['insights']], ['claim-1','claim-0','claim-2'])
        self.assertEqual(w.intelligence.status, 'off')
        self.assertEqual(w.components[0].id, 'TaskList-tasks')

    def test_rejects_any_unlisted_widget_claim_or_duplicate(self):
        w = example_workspace()
        choices = [
            GroqChoice(component_ids=['NewChart'], claim_indices=[]),
            GroqChoice(component_ids=[], claim_indices=[2]),
            GroqChoice(component_ids=['TaskList-tasks']*2, claim_indices=[]),
            GroqChoice(component_ids=[], claim_indices=[99]),
            GroqChoice(component_ids=[], claim_indices=[]),
        ]
        for choice in choices:
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                _apply_choice(w, choice)

    def test_payload_is_bounded_does_not_contain_full_db_records(self):
        p = _input_payload('review blocked task t1', example_workspace())
        self.assertEqual(len(p['components']), 2)
        self.assertNotIn('datasets', p)
        self.assertNotIn('database_url', str(p))
        self.assertIn('SORYU REFERENCE EXCERPTS', p['atlas_context'])
        self.assertLessEqual(len(p['atlas_context']), 1700)

    def test_mocked_provider_success_and_json_contract(self):
        w = example_workspace()
        mock_client = MagicMock()
        response = mock_client.return_value.__enter__.return_value.post.return_value
        response.content = b'{}'
        response.json.return_value = {'choices':[{'message':{'content':json.dumps({'component_ids':['InsightPanel-insights'], 'claim_indices':[1]})}}]}
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'mock-secret', 'GROQ_MODEL':'openai/gpt-oss-20b'}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', mock_client):
            output = groq_enrich('please review t1', w)
        self.assertEqual(output.intelligence.status,'enriched')
        self.assertEqual(output.intelligence.model,'openai/gpt-oss-20b')
        args, kw = mock_client.return_value.__enter__.return_value.post.call_args
        self.assertEqual(args[0], 'https://api.groq.com/openai/v1/chat/completions')
        self.assertTrue(kw['json']['response_format']['json_schema']['strict'])
        self.assertNotIn('mock-secret', json.dumps(kw['json']))
        self.assertEqual(kw['json']['max_completion_tokens'],550)

    def test_invalid_provider_values_safe_fallback(self):
        mock_client = MagicMock()
        resp = mock_client.return_value.__enter__.return_value.post.return_value
        resp.content = b'{}'
        resp.json.return_value = {'choices':[{'message':{'content':'{"component_ids":["fake"], "claim_indices":[]}'}}]}
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'test'}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', mock_client):
            w = example_workspace()
            output = groq_enrich('show task', w)
        self.assertEqual(output.intelligence.status, 'fallback')
        self.assertEqual(output.components[0].id, 'TaskList-tasks')
        self.assertEqual(output.claims[0].text, 'Task t1 is recorded as blocked.')

    def test_daily_budget_blocks_second_call_without_network(self):
        mock_client = MagicMock()
        resp = mock_client.return_value.__enter__.return_value.post.return_value
        resp.content = b'{}'
        resp.json.return_value = {'choices':[{'message':{'content':'{"component_ids":["TaskList-tasks"],"claim_indices":[]}'}}]}
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'test',
                                     'KAIROS_GROQ_DAILY_CALL_LIMIT':'1'}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', mock_client):
            self.assertEqual(groq_enrich('show task', example_workspace()).intelligence.status, 'enriched')
            self.assertEqual(groq_enrich('show task', example_workspace()).intelligence.status, 'budget')
        self.assertEqual(mock_client.return_value.__enter__.return_value.post.call_count,1)

    def test_clarification_never_calls_model(self):
        w = example_workspace().model_copy(deep=True)
        w.status = 'clarification'
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':'test'}, clear=False), \
             patch('backend.intelligence.groq_focus.httpx.Client', side_effect=AssertionError('network used')):
            self.assertIs(groq_enrich('unknown task', w), w)


if __name__ == '__main__':
    unittest.main()
