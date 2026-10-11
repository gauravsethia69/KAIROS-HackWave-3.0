import { describe, expect, it } from 'vitest';
import { isCompanyKnowledgeQuestion } from '../ai/companyGuide';

describe('Pass 12D selective AI routing', () => {
  it('routes onboarding questions to Atlas knowledge guide', () => {
    expect(isCompanyKnowledgeQuestion('I am a new employee. How do things work at SORYU SYSTEMS?')).toBe(true);
    expect(isCompanyKnowledgeQuestion('What does Support do?')).toBe(true);
  });
  it('keeps operational requests on the database-backed workspace path', () => {
    expect(isCompanyKnowledgeQuestion('Review delayed projects for Atlas Media Group')).toBe(false);
    expect(isCompanyKnowledgeQuestion('Show Engineering workload')).toBe(false);
    expect(isCompanyKnowledgeQuestion('Explain why this project is at risk')).toBe(false);
  });
  it('mixed employee record requests stay on the authorized DB path', () => {
    expect(isCompanyKnowledgeQuestion('I am new; show my assigned tasks')).toBe(false);
  });
});
