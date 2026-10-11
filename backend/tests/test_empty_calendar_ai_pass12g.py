"""Offline tests for explaining verified empty calendar lookup, without provider calls."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from backend.intelligence.hybrid_explain import _empty_schedule_finding, explain_verified_workspace
from backend.intelligence.models import Claim
from backend.tests.test_groq_focus_pass12b import example_workspace


class EmptyCalendarExplanationTests(unittest.TestCase):
    def setUp(self):
        self.prompt='Show Jordan Lee schedule next week'
        self.plan=example_workspace().model_copy(deep=True)
        self.plan.status='not_found'
        self.plan.intent.name='team_workload_planning'
        self.plan.claims=[Claim(kind='uncertainty', text=(
            'No schedule blocks are recorded for Jordan Lee during '
            '2026-10-19 to 2026-10-25 in accessible records. '
            'An empty calendar does not prove availability.'))]
        self.plan.datasets['schedule_events']=[]
        self.plan.datasets['schedule_summary']=[{'id':'schedule-empty',
            'recorded_block_count':0,'truncated':False,
            'date_from':'2026-10-19','date_to':'2026-10-25','focus_label':'Jordan Lee'}]

    def test_qualified_empty_schedule_is_explainable_without_fabricated_ids(self):
        facts=_empty_schedule_finding(self.plan)
        self.assertEqual(len(facts),1)
        self.assertEqual(facts[0]['kind'],'uncertainty')
        self.assertEqual(facts[0]['sources'],[])
        self.assertIn('does not prove availability',facts[0]['text'])

    def test_other_not_found_intent_remains_blocked(self):
        self.plan.intent.name='project_delivery_review'
        self.assertEqual(_empty_schedule_finding(self.plan),[])
        with patch('backend.intelligence.hybrid_explain.httpx.Client',side_effect=AssertionError('network called')):
            self.assertEqual(explain_verified_workspace(self.prompt,self.plan)['status'],'fallback')

    def test_nonempty_schedule_cannot_be_treated_as_empty(self):
        self.plan.datasets['schedule_events']=[{'id':'meeting1'}]
        self.assertEqual(_empty_schedule_finding(self.plan),[])
        self.plan.datasets['schedule_events']=[]
        self.plan.datasets['schedule_summary'][0]['recorded_block_count']=1
        self.assertEqual(_empty_schedule_finding(self.plan),[])

    def test_inconsistent_window_is_rejected(self):
        self.plan.datasets['schedule_summary'][0]['date_to']='2026-11-01'
        self.assertEqual(_empty_schedule_finding(self.plan),[])

    def test_missing_uncertainty_blocks_inference(self):
        self.plan.claims=[]
        self.assertEqual(_empty_schedule_finding(self.plan),[])

    def test_truncated_calendar_is_not_considered_empty(self):
        self.plan.datasets['schedule_summary'][0]['truncated']=True
        self.assertEqual(_empty_schedule_finding(self.plan),[])

    def test_disabled_groq_consumes_no_tokens(self):
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'false','GROQ_API_KEY':'unused'}), \
             patch('backend.intelligence.hybrid_explain.httpx.Client',side_effect=AssertionError('network called')):
            self.assertEqual(explain_verified_workspace(self.prompt,self.plan)['status'],'off')

    def test_mock_model_can_explain_absence_without_inventing_bookings(self):
        mock=MagicMock()
        reply=mock.return_value.__enter__.return_value.post.return_value
        reply.content=b'{"mock":true}'
        reply.json.return_value={'choices':[{'message':{'content':json.dumps({'points':[
             {'claim_index':0,'explanation':
              'There are no recorded blocks for Jordan Lee in the selected week. '
              'This does not confirm availability; check with the calendar organizer.'}]})}}],
             'usage':{'prompt_tokens':133,'completion_tokens':62}}
        with patch.dict(os.environ,{'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'fake-test-only'}), \
             patch('backend.intelligence.hybrid_explain.httpx.Client',mock), \
             patch('backend.intelligence.hybrid_explain._budget_allows',return_value=True):
            response=explain_verified_workspace(self.prompt,self.plan,viewer='test-pass12g-1')
        self.assertEqual(response['status'],'enriched')
        self.assertEqual(response['points'][0]['evidence_ids'],[])
        self.assertIn('does not confirm availability',response['points'][0]['explanation'])
        payload=mock.return_value.__enter__.return_value.post.call_args.kwargs['json']
        self.assertIn('does not prove availability',json.dumps(payload))
        self.assertNotIn('fake-test-only',json.dumps(payload))
        mock.return_value.__enter__.return_value.post.assert_called_once()


if __name__=='__main__': unittest.main()
