"""Pass 12D.2 company-guide safe diagnostics: offline tests, no Groq calls."""
import io
import logging
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from backend.intelligence.company_guide import _record_safe_failure, GuideSummary


class CompanyGuideSafeDiagnosticsTests(unittest.TestCase):
    def check(self, error, expected):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger('kairos.company_guide')
        logger.addHandler(handler)
        try:
            _record_safe_failure(error)
        finally:
            logger.removeHandler(handler)
        self.assertIn('cause=' + expected, output.getvalue())
        self.assertNotIn('SENSITIVE_PROMPT_VALUE', output.getvalue())
        self.assertNotIn('SENSITIVE_KEY_VALUE', output.getvalue())

    def test_http_429_categorized_without_leaking_response(self):
        request = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
        response = httpx.Response(429, request=request, text='SENSITIVE_PROMPT_VALUE SENSITIVE_KEY_VALUE')
        self.check(httpx.HTTPStatusError('secret', request=request, response=response), 'provider_http_429')

    def test_http_400_categorized(self):
        request = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
        response = httpx.Response(400, request=request, text='SENSITIVE_KEY_VALUE')
        self.check(httpx.HTTPStatusError('secret', request=request, response=response), 'provider_http_400')

    def test_timeout_categorized(self):
        self.check(httpx.ReadTimeout('SENSITIVE_KEY_VALUE'), 'provider_timeout')

    def test_network_categorized(self):
        self.check(httpx.ConnectError('SENSITIVE_KEY_VALUE'), 'provider_network')

    def test_invalid_shape_categorized(self):
        self.check(KeyError('SENSITIVE_PROMPT_VALUE'), 'provider_response_shape')

    def test_schema_validation_categorized(self):
        with self.assertRaises(ValidationError) as ctx:
            GuideSummary.model_validate({'items': []})
        self.check(ctx.exception, 'schema_validation')

    def test_content_validation_categorized(self):
        self.check(ValueError('SENSITIVE_PROMPT_VALUE'), 'source_citation_or_content_validation')


if __name__ == '__main__':
    unittest.main()
