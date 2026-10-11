"""Pass 12D.3: offline company-guide response schema regression tests."""
import io
import json
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from backend.intelligence.company_guide import (
    GuideSummary, _parse_provider_summary, _validate_summary,
    _record_safe_failure, enrich_guide, prepare_guide,
)


class CompanyGuideSchemaTests(unittest.TestCase):
    def test_single_valid_cited_summary_no_longer_falls_back(self):
        parsed = _parse_provider_summary(json.dumps({'items': [{'chunk_id': 'atlas-p01-s01',
                         'summary': 'SORYU uses four recorded products and maintains verified product information in its database.'}]}))
        self.assertEqual(len(parsed.items), 1)

    def test_over_320_char_but_under_720_char_accepted(self):
        parsed = _parse_provider_summary(json.dumps({'items': [{'chunk_id': 'atlas-p01-s01',
                          'summary': 'The passage provides company information. ' * 12}]}))
        self.assertEqual(len(parsed.items), 1)

    def test_empty_rejected(self):
        with self.assertRaises(ValidationError):
            _parse_provider_summary('{"items":[]}')

    def test_extra_items_clamped_to_six(self):
        items = [{'chunk_id': f'c-{i}', 'summary': 'This summary describes the cited reference only.'} for i in range(9)]
        parsed = _parse_provider_summary(json.dumps({'items':items}))
        self.assertEqual(len(parsed.items), 6)

    def test_invalid_json_not_repaired(self):
        with self.assertRaises(json.JSONDecodeError):
            _parse_provider_summary('{"items": [')

    def test_hallucinated_source_id_rejected(self):
        parsed = _parse_provider_summary(json.dumps({'items': [{'chunk_id': 'fake-source',
             'summary': 'This claims to be from an original company reference.'}]}))
        guide = prepare_guide('I am a new employee, how do things work?')
        with self.assertRaises(ValueError):
            _validate_summary(parsed, guide['passages'])

    def test_prohibited_policy_claim_still_rejected(self):
        guide = prepare_guide('I am a new employee, how do things work?')
        source = guide['passages'][0]
        parsed = _parse_provider_summary(json.dumps({'items': [{'chunk_id': source['id'],
                   'summary': 'This is an official company policy that all employees must follow.'}]}))
        with self.assertRaises(ValueError):
            _validate_summary(parsed, guide['passages'])

    def test_safe_schema_error_logging(self):
        try:
            GuideSummary.model_validate({'items': [{'chunk_id': 'SENSITIVE_SOURCE', 'summary': 'private' * 130}]})
            self.fail('expected validation error')
        except ValidationError as err:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            logger = logging.getLogger('kairos.company_guide')
            logger.addHandler(handler)
            try:
                _record_safe_failure(err)
            finally:
                logger.removeHandler(handler)
            output = stream.getvalue()
            self.assertIn('cause=schema_validation', output)
            self.assertIn('detail=summary:string_too_long', output)
            self.assertNotIn('SENSITIVE_SOURCE', output)
            self.assertNotIn('private', output)

    def test_end_to_end_enrichment_mock_no_provider_calls(self):
        guide = prepare_guide('I am a new employee. How do things work?')
        sources = guide['passages']
        self.assertGreaterEqual(len(sources), 2)
        content = json.dumps({'items':[{'chunk_id': sources[0]['id'],
          'summary':'The company reference names four recorded products with database-grounded descriptions.'}]})
        mock_client = MagicMock()
        response = mock_client.return_value.__enter__.return_value.post.return_value
        response.content = b'{"mock":true}'
        response.json.return_value = {'choices':[{'message':{'content':content}}],
                                        'usage': {'prompt_tokens': 120, 'completion_tokens': 40}}
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED': 'true', 'GROQ_API_KEY':'UNIT_TEST_ONLY',
                                     'GROQ_MODEL':'openai/gpt-oss-20b'}), \
             patch('backend.intelligence.company_guide.httpx.Client', mock_client), \
             patch('backend.intelligence.company_guide._budget_allows', return_value=True):
            answer = enrich_guide('I am a new employee. How do things work?', viewer='schema-fix-test-viewer')
        self.assertEqual(answer['status'], 'enriched')
        self.assertEqual(len(answer['items']), 1)
        self.assertEqual(answer['items'][0]['page'], sources[0]['page'])
        mock_client.return_value.__enter__.return_value.post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
