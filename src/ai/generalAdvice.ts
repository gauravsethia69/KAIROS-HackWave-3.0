import { z } from 'zod';
import { apiRequest } from '../lib/api';

import { routeKairosQuestion } from './intentRouting';

/** General guidance is selected only when operational evidence is not requested. */
export function isGeneralAdviceQuestion(input: string): boolean {
  return routeKairosQuestion(input) === 'general_advice';
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
