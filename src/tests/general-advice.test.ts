import { describe, expect, it } from 'vitest';
import { isGeneralAdviceQuestion } from '../ai/generalAdvice';

describe('Pass 12E intentional generic AI routing', () => {
  it('recognizes generic guidance', () => {
    for (const q of ['How to increase sales?', 'How can we increase sales?', 'What can we do to increase sales?',
      'How do we improve customer retention?', 'How can I improve productivity?',
      'How to make meetings effective?', 'What are some ways to improve team collaboration?']) {
      expect(isGeneralAdviceQuestion(q)).toBe(true);
    }
  });
  it('preserves established PostgreSQL and onboarding routes', () => {
    for (const q of ['Show Engineering workload','Show our sales metrics',
      'Review delayed projects for Atlas Media Group', 'How can we increase sales for OrbitPay?',
      'Why did our sales drop last month?', 'How to schedule a meeting?',
      'I am a new employee. How do things work?', 'How to increase sales based on our actual recorded metrics?']) {
      expect(isGeneralAdviceQuestion(q)).toBe(false);
    }
  });
});
