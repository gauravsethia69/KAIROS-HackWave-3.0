import { z } from 'zod';
import { apiRequest } from '../lib/api';

/** Strictly generic strategy prompts. No company records, no writes, no SQL. */
const advicePrefix = /^(?:how\s+(?:can|could|should|do|would)\s+(?:we|i|our\s+team|a\s+company|businesses)\s+|how\s+to\s+|what\s+can\s+we\s+do\s+to\s+|what\s+strategies\s+(?:can|could)\s+(?:help\s+)?|what\s+are\s+(?:some\s+)?(?:ways|strategies|tips|ideas|best\s+practices)\s+(?:to|for)\s+|(?:give|suggest|recommend)\s+(?:me\s+|us\s+)?(?:some\s+)?(?:ways|strategies|tips|ideas)\s+(?:to|for)\s+|(?:ways|strategies|tips|ideas)\s+(?:to|for)\s+)/i;
const adviceTopics = /\b(?:sales|selling|revenue|conversion|leads?|marketing|customer\s+(?:retention|satisfaction|engagement|experience|support)|customer\s+service|communication|teamwork|collaboration|productivity|team\s+productivity|meeting\s+(?:quality|effectiveness|efficiency)|meetings|employee\s+(?:engagement|motivation)|business\s+growth|efficiency|onboarding|project\s+management|customer\s+acquisition|brand\s+awareness|support\s+quality|feedback|product\s+adoption)\b/i;
const operational = /\b(?:show|list|find|analy[sz]e|investigate|fetch|query|dashboard|report|compare|chart|graph|actual|recorded|our\s+(?:current|actual|last|previous|historical|specific)|last\s+(?:week|month|quarter|year)|this\s+(?:week|month|quarter)|who\s+(?:owns|is|are)|assigned|schedule|book|create|delete|update|database|my\s+(?:tasks?|projects?|clients?|calendar|schedule|meetings?)|northstar|orbitpay|atlas\s+media|acme|nova\s+studio)\b/i;

export function isGeneralAdviceQuestion(input: string): boolean {
  const q = input.trim().replace(/\s+/g, ' ');
  return q.length >= 8 && q.length <= 550 && advicePrefix.test(q) && adviceTopics.test(q) && !operational.test(q);
}

const adviceSchema = z.object({
  status: z.enum(['enriched', 'off', 'budget', 'fallback', 'not_general']),
  model: z.string().optional(), cached: z.boolean().optional(),
  advice: z.object({
    title: z.string(), introduction: z.string(),
    steps: z.array(z.object({action:z.string(), why:z.string()})).max(6), caution:z.string(),
  }).nullable(),
});
export type GeneralAdviceResult = z.infer<typeof adviceSchema>;

export async function fetchGeneralAdvice(question: string): Promise<GeneralAdviceResult> {
  const response: unknown = await apiRequest('/api/intelligence/general-advice/answer', {
    method: 'POST', body: JSON.stringify({input:question}),
  });
  return adviceSchema.parse(response);
}
