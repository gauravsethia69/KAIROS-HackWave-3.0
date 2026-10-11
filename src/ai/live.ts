import { z } from 'zod';
import { apiRequest } from '../lib/api';
import { workspacePlanSchema } from '../types/workspace';
import type { WorkspacePlan } from '../types/workspace';
const responseSchema = z.object({ plan: workspacePlanSchema, source: z.enum(['live', 'deterministic', 'fallback']), message: z.string() }).strict();
export async function planLive(input: string, previous: WorkspacePlan, useAI = true) {
  return responseSchema.parse(await apiRequest('/api/workspace/plan', { method: 'POST', body: JSON.stringify({ input, previous, use_ai: useAI }) }));
}
