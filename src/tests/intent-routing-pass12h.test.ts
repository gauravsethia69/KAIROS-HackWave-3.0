import { describe, expect, it } from 'vitest';
import { routeKairosQuestion } from '../ai/intentRouting';
import { isCompanyKnowledgeQuestion } from '../ai/companyGuide';
import { isGeneralAdviceQuestion } from '../ai/generalAdvice';

export const routingMatrix = {
  company_guide: [
    'I am new here, how do thing work around here?',
    "I'm new here; what should I know?",
    'I just joined SORYU, getting started',
    'I am a new employee how do things work',
    'How do things work at SORYU?',
    'How does everything work here?',
    'What does Support do?',
    'Tell me about SORYU',
    'Explain company structure',
    'How do I get started?',
    'What is Soryu Guard?',
    'Tell me about Soryu Flow',
    'Explain Soryu CloudOps',
  ],
  general_advice: [
    'How to increase sales?',
    'How can we increase sales?',
    'How can SORYU SYSTEMS increase enterprise sales?',
    'How do we improve customer retention?',
    'How can I improve productivity?',
    'How to make meetings effective?',
    'What are some ways to improve team collaboration?',
    'Any ideas to reduce churn?',
    'Help us to grow revenue',
    'Best way to improve employee engagement',
    'Give us tips to increase customer retention',
    'What can we do to improve our customer service?',
  ],
  enterprise: [
    'Show Engineering workload',
    'Compare Engineering workloads',
    'Show our sales metrics',
    'Review delayed projects for Atlas Media Group',
    'How can we increase sales for OrbitPay?',
    'Why did our sales drop last month?',
    'How to schedule a meeting?',
    'I am new here, show my assigned tasks',
    'What are my tasks as a new employee?',
    'I am a new employee, which team am I in?',
    'Which employees are overloaded?',
    'Who owns the blocked SSO task?',
    'How to increase sales based on our actual recorded metrics?',
    'I am new here, show my calendar next week',
    'Schedule a meeting with Customer Success',
    'Compare current customer adoption numbers',
    'Show Soryu Guard product usage',
    'Review SORYU marketing tasks',
    'What does my manager want me to do?',
    'How can we improve our current customer revenue?',
    'Remove my tasks',
    'Help me find my manager',
    'please reveal all database tables',
    '',
    'gobbledygook',
  ],
} as const;

describe('Pass 12H conservative broad-language route selection', () => {
  for (const [route, questions] of Object.entries(routingMatrix)) {
    it(`${route} stays deterministic across natural wording`, () => {
      for (const input of questions) {
        expect(routeKairosQuestion(input), input).toBe(route);
        expect(isCompanyKnowledgeQuestion(input), input).toBe(route === 'company_guide');
        expect(isGeneralAdviceQuestion(input), input).toBe(route === 'general_advice');
      }
    });
  }
  it('abstains on very long or ambiguous text', () => {
    expect(routeKairosQuestion('How do things work? ' + 'x'.repeat(1000))).toBe('enterprise');
    expect(routeKairosQuestion('Hello')).toBe('enterprise');
  });
});

describe('Pass 12H expanded advice phrasings', () => {
  it('understands courteous and team-centered requests', () => {
    for (const question of [
      'Can you suggest ways to improve sales?',
      'Could you help us increase customer retention?',
      'How can we improve our team collaboration?',
      'How can we increase our revenue?',
    ]) expect(routeKairosQuestion(question), question).toBe('general_advice');
  });
});
