import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

describe('Pass 12D.1 company guide manual AI invocation', () => {
  const app = readFileSync(new URL('../app/App.tsx', import.meta.url), 'utf8');
  const view = readFileSync(new URL('../components/intelligence/CompanyGuide.tsx', import.meta.url), 'utf8');
  it('does not call the AI when Atlas sources are fetched', () => {
    const branch = app.split('if (supabase && !selection && isCompanyKnowledgeQuestion(text))')[1]
      ?.split('if (supabase)')[0] ?? '';
    expect(branch).not.toContain('explainCompanyGuide(text)');
    expect(branch).toContain('companyGuideQuestion.current = text');
  });
  it('offers a visible user-triggered AI button with loading and fallback status', () => {
    expect(view).toContain('Explain with AI');
    expect(view).toContain('onClick={onExplain}');
    expect(view).toContain('Groq could not produce a verified explanation');
    expect(view).toContain('company-guide-ai-answer');
  });
});
