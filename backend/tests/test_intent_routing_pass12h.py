"""Pure local route tests, no live Groq/API/database calls."""
import unittest

from backend.intelligence.company_guide import is_onboarding, prepare_guide
from backend.intelligence.general_advice import is_general_advice


class NaturalLanguageRoutingTests(unittest.TestCase):
    def test_new_employee_paraphrases_receive_recorded_atlas_material(self):
        cases = [
            'I am new here, how do thing work around here?',
            "I'm new here, what should I know?",
            'I just joined SORYU, getting started',
            'I am a new employee how do things work',
            'How do things work at SORYU?',
            'How does everything work here?',
            'How do I get started?',
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_onboarding(phrase))
                answer = prepare_guide(phrase)
                self.assertEqual(answer['status'], 'ready')
                self.assertEqual([x['page'] for x in answer['passages']], [1, 2, 3, 4, 5])

    def test_advice_paraphrases_use_existing_bounded_provider_gate(self):
        positive = [
            'How to increase sales?', 'How can we increase sales?',
            'How can SORYU SYSTEMS increase enterprise sales?',
            'How do we improve customer retention?',
            'How can I improve productivity?',
            'How to make meetings effective?',
            'What are some ways to improve team collaboration?',
            'Any ideas to reduce churn?', 'Help us to grow revenue',
            'Best way to improve employee engagement',
            'Give us tips to increase customer retention',
            'What can we do to improve our customer service?',
            'Can you suggest ways to improve sales?',
            'Could you help us increase customer retention?',
            'How can we improve our team collaboration?',
            'How can we increase our revenue?',
        ]
        for phrase in positive:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_general_advice(phrase))

    def test_operational_requests_are_not_generic_ai_advice(self):
        cases = [
            'Show Engineering workload', 'Compare Engineering workloads',
            'Show our sales metrics', 'Review delayed projects for Atlas Media Group',
            'How can we increase sales for OrbitPay?',
            'Why did our sales drop last month?',
            'How to schedule a meeting?',
            'What are my tasks as a new employee?',
            'Which employees are overloaded?',
            'How to increase sales based on our actual recorded metrics?',
            'Schedule a meeting with Customer Success',
            'Compare current customer adoption numbers',
            'How can we improve our current customer revenue?',
        ]
        for phrase in cases:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_general_advice(phrase))

if __name__ == '__main__':
    unittest.main()
