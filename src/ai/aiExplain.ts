/** Pass 12D: explicit, separate explanation of authenticated PostgreSQL facts.
 * No frontend-supplied claims, SQL, project rows, evidence or statuses.
 */
import { z } from 'zod';
import { apiRequest } from '../lib/api';
import type { EnterpriseEntity } from './enterprise';

const responseSchema = z.object({
  status: z.enum(['off','fallback','budget','enriched']),
  model: z.string().optional(), cached: z.boolean().optional(),
  points: z.array(z.object({
    claim_index: z.number().int(), finding: z.string(), explanation: z.string(),
    evidence_ids: z.array(z.string()),
  })).max(3),
  atlas_sources: z.array(z.object({
    id: z.string(), page: z.number().int(), source_id: z.string(),
    status: z.enum(['proposed','reference']), text: z.string(),
  })).max(2),
});
export type WorkspaceExplanation = z.infer<typeof responseSchema>;

export async function explainWorkspace(question: string, selection?: EnterpriseEntity): Promise<WorkspaceExplanation> {
  const data: unknown = await apiRequest('/api/intelligence/workspace/explain', {
    method: 'POST', body: JSON.stringify({input:question,
      ...(selection ? {selection:{entity_type:selection.entity_type, entity_id:selection.entity_id}} : {})}),
  });
  return responseSchema.parse(data);
}

const usageSchema = z.object({
  scope: z.literal('this_backend_process_only'), billing_authority:z.string(), recorded_at:z.string(),
  by_feature: z.record(z.object({attempts:z.number(),responses:z.number(),
    input_tokens:z.number(),output_tokens:z.number(),unknown_usage:z.number()})),
});
export type AITokenUsage = z.infer<typeof usageSchema>;
export async function fetchAIUsage(): Promise<AITokenUsage> {
  const data: unknown = await apiRequest('/api/intelligence/ai/usage');
  return usageSchema.parse(data);
}
