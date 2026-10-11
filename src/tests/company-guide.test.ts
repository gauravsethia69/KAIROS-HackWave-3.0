import { describe, expect, it } from 'vitest';
import { isCompanyKnowledgeQuestion } from '../ai/companyGuide';

describe('Pass 12C company knowledge routing', () => {
  it('routes general onboarding to the PDF guide', () => {
    expect(isCompanyKnowledgeQuestion('I am a new employee how do things work')).toBe(true);
    expect(isCompanyKnowledgeQuestion('I just joined SORYU, getting started')).toBe(true);
    expect(isCompanyKnowledgeQuestion('What does Support do?')).toBe(true);
    expect(isCompanyKnowledgeQuestion('Tell me about SORYU')).toBe(true);
  });
  it('never diverts operational requests away from the live database', () => {
    for (const question of [
      'Show Engineering workload', 'Prepare for the next OrbitPay client meeting',
      'What are my tasks as a new employee?', 'Show my schedule for next week',
      'Review delayed projects and blocking tasks', 'Which employees are overloaded?',
      'I am a new employee show my assigned projects',
      'I am a new employee, which team am I in?',
    ]) expect(isCompanyKnowledgeQuestion(question)).toBe(false);
  });
});
