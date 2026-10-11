"""Fail-fast tests; no Groq account, SQL or network access."""
import os
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from backend.intelligence import groq_deadline
from backend.tests.test_groq_focus_pass12b import example_workspace


class GroqDeadlineSafetyTests(unittest.TestCase):
    def test_off_is_instant_and_does_not_start_background_work(self):
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED': 'false'}, clear=False), patch.object(groq_deadline, 'groq_enrich', side_effect=AssertionError('no Groq')):
            self.assertIs(groq_deadline.groq_enrich_with_deadline('test', w), w)

    def test_no_key_is_instant(self):
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true', 'GROQ_API_KEY':''}, clear=False), patch.object(groq_deadline, 'groq_enrich', side_effect=AssertionError('no Groq')):
            self.assertIs(groq_deadline.groq_enrich_with_deadline('test', w), w)

    def test_fast_enrichment_can_return(self):
        def fast(_, w):
            w.intelligence.status = 'enriched'
            return w
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'fake','KAIROS_GROQ_MAX_WAIT_SECONDS':'1'}, clear=False), patch.object(groq_deadline, 'groq_enrich', side_effect=fast):
            result = groq_deadline.groq_enrich_with_deadline('test', w)
            self.assertEqual(result.intelligence.status, 'enriched')
            self.assertIsNot(result, w)
            self.assertEqual(w.intelligence.status, 'off')

    def test_slow_enrichment_cannot_delay_or_mutate_original(self):
        def slow(_, w):
            sleep(.55)
            w.title = 'LATE MODEL MUTATION'
            w.intelligence.status = 'enriched'
            return w
        w = example_workspace()
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'fake','KAIROS_GROQ_MAX_WAIT_SECONDS':'0.25'}, clear=False), patch.object(groq_deadline, 'groq_enrich', side_effect=slow):
            start=monotonic()
            result=groq_deadline.groq_enrich_with_deadline('test', w)
            self.assertLess(monotonic()-start, .5)
            self.assertIs(result, w)
            self.assertEqual(result.intelligence.status, 'fallback')
            sleep(.40)
            self.assertNotEqual(w.title, 'LATE MODEL MUTATION')
            self.assertEqual(w.intelligence.status, 'fallback')

    def test_busy_provider_does_not_queue(self):
        with patch.dict(os.environ, {'KAIROS_GROQ_ENABLED':'true','GROQ_API_KEY':'fake'}, clear=False), patch.object(groq_deadline._slots, 'acquire', return_value=False):
            w = example_workspace()
            self.assertIs(groq_deadline.groq_enrich_with_deadline('test',w), w)
            self.assertEqual(w.intelligence.status, 'fallback')

if __name__=='__main__': unittest.main()
