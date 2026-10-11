"""Regression tests for concise Groq Guide summary text (no network calls)."""
import json
import unittest
from unittest.mock import patch, MagicMock

from pydantic import ValidationError
from backend.intelligence.company_guide import (
    _parse_provider_summary, _validate_summary, enrich_guide, prepare_guide,
)

QUESTION = 'I am a new employee. How do things work?'


class GuideShortSummaryTests(unittest.TestCase):
    def setUp(self):
        self.sources = prepare_guide(QUESTION)['passages']
        self.assertGreaterEqual(len(self.sources), 2)
        self.source_id = self.sources[0]['id']

    def parse(self, items):
        return _parse_provider_summary(json.dumps({'items': items}))

    def test_short_cited_phrase_no_longer_fails(self):
        for summary in ('Teams.', 'Go.', 'OK', 'A'):
            with self.subTest(summary=summary):
                value = self.parse([{'chunk_id': self.source_id, 'summary': summary}])
                accepted = _validate_summary(value, self.sources)
                self.assertEqual(accepted[0]['summary'], summary)
                self.assertEqual(accepted[0]['citation'], self.sources[0]['citation'])

    def test_one_blank_does_not_discard_a_second_valid_citation(self):
        value = self.parse([{'chunk_id': self.source_id, 'summary': '   '},
                            {'chunk_id': self.sources[1]['id'], 'summary': 'Teams.'}])
        self.assertEqual(len(value.items), 1)
        self.assertEqual(_validate_summary(value, self.sources)[0]['summary'], 'Teams.')

    def test_all_blank_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.parse([{'chunk_id': self.source_id, 'summary': ' '}])

    def test_whitespace_is_trimmed(self):
        self.assertEqual(_validate_summary(self.parse([{'chunk_id': self.source_id,
           'summary': '  Teams.  '}]), self.sources)[0]['summary'], 'Teams.')

    def test_unknown_citation_is_still_rejected(self):
        with self.assertRaises(ValueError):
            _validate_summary(self.parse([{'chunk_id': 'made-up-id', 'summary': 'OK'}]), self.sources)

    def test_policy_claim_is_still_rejected(self):
        with self.assertRaises(ValueError):
            _validate_summary(self.parse([{'chunk_id': self.source_id,
                'summary': 'This is official company policy.'}]), self.sources)

    def test_duplicate_citations_are_still_rejected(self):
        with self.assertRaises(ValueError):
            _validate_summary(self.parse([{'chunk_id': self.source_id, 'summary': 'One.'},
                {'chunk_id': self.source_id, 'summary': 'Two.'}]), self.sources)

    def test_url_is_still_rejected(self):
        with self.assertRaises(ValueError):
            _validate_summary(self.parse([{'chunk_id': self.source_id,
                'summary': 'Read https://invalid.example now.'}]), self.sources)

    def test_short_summary_end_to_end_offline_mock(self):
        response = {'choices': [{'message': {'content': json.dumps({'items': [
            {'chunk_id': self.source_id, 'summary': 'Teams.'}]})}}],
            'usage': {'prompt_tokens': 123, 'completion_tokens': 9}}
        mock_client = MagicMock()
        reply = mock_client.return_value.__enter__.return_value.post.return_value
        reply.content = b'{"placeholder":true}'
        reply.json.return_value = response
        with patch.dict('os.environ', {'KAIROS_GROQ_ENABLED': 'true',
                 'GROQ_API_KEY': 'FAKE_TEST_ONLY', 'GROQ_MODEL':'openai/gpt-oss-20b'}), \
             patch('backend.intelligence.company_guide.httpx.Client', mock_client), \
             patch('backend.intelligence.company_guide._budget_allows', return_value=True):
            result = enrich_guide(QUESTION, viewer='short-summary-test-12d4')
        self.assertEqual(result['status'], 'enriched')
        self.assertEqual(result['items'][0]['summary'], 'Teams.')
        mock_client.return_value.__enter__.return_value.post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
