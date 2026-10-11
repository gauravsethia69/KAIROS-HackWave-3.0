/** Thin, runtime-validated adapter between deterministic enterprise v2 and existing v1 widgets.
 * This module performs no AI calls and grants no authorization; FastAPI enforces membership.
 */
import { z } from 'zod';
import { apiRequest } from '../lib/api';
import { componentTypes, bindings, workspacePlanSchema } from '../types/workspace';
import type { WorkspacePlan } from '../types/workspace';
import type { Dataset } from '../data/demo';

const entitySchema = z.object({ entity_type: z.string(), entity_id: z.string() }).passthrough();
const evidenceSchema = z.object({
  id: z.string(), source_type: z.enum(['database', 'document']), title: z.string(),
  field: z.string(), navigation: z.object({ kind: z.enum(['entity_detail', 'knowledge_document']), entity: entitySchema.nullish(), document_id: z.string().nullish(), section: z.string().nullish() }).passthrough(),
}).passthrough();
const claimSchema = z.object({kind: z.enum(['observation', 'calculation', 'uncertainty', 'proposed_action']), text: z.string(), evidence_ids: z.array(z.string())});
const componentSchema = z.object({
  id: z.string(), type: z.enum(componentTypes), title: z.string(), priority: z.number(), order: z.number(),
  size: z.enum(['small','medium','wide']), props: z.object({selector: z.enum(['clients','meetings','communications','usage','tasks','projects','issues','insights','activity']), record_ids: z.array(z.string()), binding: z.literal('response.datasets')}), evidence_ids: z.array(z.string()), reason: z.string(),
}).passthrough();
const responseSchema = z.object({
  intelligence: z.object({ status: z.enum(['off','enriched','fallback','budget']), model: z.string().nullish() }).optional(),
  schemaVersion: z.literal(2), source: z.literal('deterministic-enterprise'),
  status: z.enum(['ready', 'partial', 'clarification', 'not_found', 'unsupported']), title: z.string(),
  intent: z.object({
    name: z.string(), clarification: z.object({question: z.string(), candidates: z.array(z.object({entity: entitySchema, label: z.string()} ).passthrough()), suggestions: z.array(z.string())}).nullish(),
    compare: z.boolean().optional(), unresolved_only: z.boolean().optional(), presentation: z.string().optional(),
    date_from: z.string().nullish(), date_to: z.string().nullish(),
  }).passthrough(),
  context_token: z.string().nullish(), components: z.array(componentSchema), datasets: z.record(z.array(z.record(z.unknown()))),
  evidence: z.array(evidenceSchema), claims: z.array(claimSchema), explanations: z.array(z.string()), limitations: z.array(z.string()), integration_requirements: z.array(z.string()),
}).passthrough();
export type EnterpriseResponse = z.infer<typeof responseSchema>;
export type EnterpriseEvidence = z.infer<typeof evidenceSchema>;
export type EnterpriseEntity = z.infer<typeof entitySchema>;

const text = (v: unknown) => v == null ? '' : String(v);
const num = (v: unknown) => typeof v === 'number' && Number.isFinite(v) ? v : Number(v) || 0;
const bool = (v: unknown) => v === true;
const rows = (payload: EnterpriseResponse, field: string) => payload.datasets[field] || [];

/** Convert only records returned by the authorized v2 response; NEVER mix demo rows into this result. */
export function enterpriseDataset(payload: EnterpriseResponse): Dataset {
  return {
    clients: rows(payload,'clients').map(r => ({id:text(r.id), name:text(r.name), sector:text(r.sector), contact:text(r.contact), email:text(r.email), owner:text(r.owner), plan:text(r.plan), seats:num(r.seats), health:text(r.health)})),
    meetings: rows(payload,'meetings').map(r => ({id:text(r.id), client_id:text(r.client_id), title:text(r.title), date:text(r.date), summary:text(r.summary), attendees:text(r.attendees), upcoming:bool(r.upcoming)})),
    communications: rows(payload,'communications').map(r => ({id:text(r.id), client_id:text(r.client_id), date:text(r.date), author:text(r.author), channel:text(r.channel), message:text(r.message)})),
    usage: rows(payload,'usage').map(r => ({id:text(r.id), client_id:text(r.client_id), date:text(r.date), active_users:num(r.active_users), sessions:num(r.sessions), errors:num(r.errors)})),
    projects: rows(payload,'projects').map(r => ({id:text(r.id), client_id:text(r.client_id), name:text(r.name), owner:text(r.owner), progress:num(r.progress), expected:num(r.expected), due_date:text(r.due_date), status:text(r.status)})),
    tasks: rows(payload,'tasks').map(r => ({id:text(r.id), client_id:text(r.client_id), project_id:text(r.project_id), title:text(r.title), owner:text(r.owner), due_date:text(r.due_date), status:text(r.status), priority:text(r.priority)})),
    issues: rows(payload,'issues').map(r => ({id:text(r.id), client_id:text(r.client_id), project_id:text(r.project_id), title:text(r.title), date:text(r.date), status:text(r.status), severity:text(r.severity), owner:text(r.owner), detail:text(r.detail)})),
    activity: rows(payload,'activity').map(r => ({id:text(r.id), date:text(r.event_time), title:text(r.event_type), text:text(r.description), label:text(r.severity)})),
  };
}

const legacyIntent: Record<string, WorkspacePlan['intent']> = {
  client_meeting_prep: 'meeting', product_usage_investigation: 'usage', project_delivery_review: 'projects',
  support_incident_command: 'projects', team_workload_planning: 'projects', executive_briefing: 'projects',
  ownership_lookup: 'projects', entity_lookup: 'projects',
};

/** A validated presentation-only v1 plan for already registered widgets, never a fabricated dataset. */
export function adaptEnterprisePlan(payload: EnterpriseResponse): WorkspacePlan | null {
  const allowed = payload.components.filter(component =>
    component.props.selector !== 'insights' &&
    bindings[component.type].includes(component.props.selector) &&
    component.props.record_ids.every(id => rows(payload,component.props.selector).some(r => r.id === id))
  );
  if (!allowed.length) return null;
  const layout = allowed.map(component => ({
    id: component.id.slice(0,64), type: component.type, title: component.title.slice(0,100),
    selector: component.props.selector, priority: Math.max(1,Math.min(10,component.priority)),
    size: component.size, order: Math.max(0,Math.min(30,component.order)), reason: component.reason.slice(0,500) || 'Selected using recorded company evidence.',
  }));
  // v1's selectedEntityIds only permits acme/nova. Keep it empty, because the server
  // already scoped ALL enterprise records by the verified employee's authorization.
  const dates = payload.intent.date_from && payload.intent.date_to;
  const span = dates ? Math.round((Date.parse(payload.intent.date_to!)-Date.parse(payload.intent.date_from!))/86400000)+1 : 14;
  const days = ([7,14,30] as const).reduce((a,b)=>Math.abs(a-span)<=Math.abs(b-span)?a:b);
  return workspacePlanSchema.parse({
    schemaVersion: 1, intent: legacyIntent[payload.intent.name] || 'projects', title: payload.title.slice(0,140),
    selectedEntityIds: [], filters: { days, unresolvedOnly: Boolean(payload.intent.unresolved_only), compare: Boolean(payload.intent.compare) },
    layout, explanations: (payload.explanations.length ? payload.explanations : ['Components were selected from live, authorized SORYU records.']).slice(0,16).map(s=>s.slice(0,500)),
  });
}

export async function planEnterprise(input: string, contextToken?: string | null, selection?: EnterpriseEntity): Promise<EnterpriseResponse> {
  const response: unknown = await apiRequest('/api/intelligence/workspace/plan', {
    method:'POST', body:JSON.stringify({input, ...(contextToken ? {context_token:contextToken}:{}), ...(selection ? {selection:{entity_type:selection.entity_type, entity_id:selection.entity_id}}:{})}),
  });
  const parsed = responseSchema.parse(response);
  // Enforce evidence integrity in the browser as well as FastAPI.
  const ids = new Set(parsed.evidence.map(e=>e.id));
  if (parsed.claims.some(c=>c.evidence_ids.some(id=>!ids.has(id))) || parsed.components.some(c=>c.evidence_ids.some(id=>!ids.has(id)))) {
    throw new Error('Backend evidence references are incomplete.');
  }
  if (parsed.components.some(c=>!bindings[c.type].includes(c.props.selector))) throw new Error('Backend returned an unregistered component binding.');
  return parsed;
}
