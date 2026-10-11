/** Pass 12C: standalone, citeable SORYU knowledge answers.
 * Never routes operational DB questions into the PDF-only path.
 */
import { z } from 'zod';
import { apiRequest } from '../lib/api';

const passageSchema = z.object({
  id: z.string(), source_id: z.string(), page: z.number().int(), title: z.string(),
  section: z.string(), status: z.enum(['reference', 'proposed']), text: z.string(), citation: z.string(),
});
const guideSchema = z.object({
  title: z.string(), subtitle: z.string(), source: z.string(), authority: z.string(),
  status: z.enum(['ready', 'not_found']), passages: z.array(passageSchema).max(10),
});
const aiSchema = z.object({
  status: z.enum(['off','budget','fallback','enriched']), model: z.string().optional(),
  items: z.array(z.object({
    chunk_id: z.string(), summary: z.string(), citation: z.string(), page: z.number(),
    status: z.enum(['reference','proposed']),
  })).max(6),
});
export type CompanyGuideData = z.infer<typeof guideSchema>;
export type CompanyGuideEnrichment = z.infer<typeof aiSchema>;

import { routeKairosQuestion } from './intentRouting';

export function isCompanyKnowledgeQuestion(question: string): boolean {
  return routeKairosQuestion(question) === 'company_guide';
}

export async function fetchCompanyGuide(question: string): Promise<CompanyGuideData> {
  const result: unknown = await apiRequest('/api/intelligence/company-guide/sources', {
    method: 'POST', body: JSON.stringify({input: question}),
  });
  return guideSchema.parse(result);
}

export async function explainCompanyGuide(question: string): Promise<CompanyGuideEnrichment> {
  const result: unknown = await apiRequest('/api/intelligence/company-guide/explain', {
    method: 'POST', body: JSON.stringify({input: question}),
  });
  return aiSchema.parse(result);
}
