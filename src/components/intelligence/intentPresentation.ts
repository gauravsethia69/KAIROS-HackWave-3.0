import type { EnterpriseResponse } from '../../ai/enterprise';

export type IntentAppearance = {
  kind: 'meeting' | 'usage' | 'project' | 'support' | 'people' | 'executive' | 'lookup';
  eyebrow: string;
  title: string;
  interfaceName: string;
  purpose: string;
};

/** Presentation copy only: the server remains the authority for facts and selected components. */
export function intentAppearance(result: EnterpriseResponse): IntentAppearance {
  const intent = result.intent.name;
  if (intent === 'client_meeting_prep') return {kind:'meeting',eyebrow:'MEETING INTELLIGENCE',title:'Meeting briefing',interfaceName:'Client briefing workspace',purpose:'Context, accountable owners and suggested discussion points'};
  if (intent === 'product_usage_investigation') return {kind:'usage',eyebrow:'PRODUCT INTELLIGENCE',title:'Usage investigation',interfaceName:'Product analytics workspace',purpose:'Usage history and supported explanations'};
  if (intent === 'project_delivery_review') return {kind:'project',eyebrow:'DELIVERY INTELLIGENCE',title:'Project health review',interfaceName:'Delivery and dependency workspace',purpose:'Progress gaps, blockers and responsible owners'};
  if (intent === 'support_incident_command') return {kind:'support',eyebrow:'INCIDENT INTELLIGENCE',title:'Incident command',interfaceName:'Support triage workspace',purpose:'Prioritized incidents and response context'};
  if (intent === 'team_workload_planning') return {kind:'people',eyebrow:'PEOPLE & TIME',title:'Schedule and capacity',interfaceName:'Calendar and workload workspace',purpose:'Recorded availability and assigned work'};
  if (intent === 'executive_briefing') return {kind:'executive',eyebrow:'BUSINESS INTELLIGENCE',title:'Executive overview',interfaceName:'Executive portfolio workspace',purpose:'Company health, risk and measured performance'};
  return {kind:'lookup',eyebrow:'ENTERPRISE INTELLIGENCE',title:'Focused enterprise answer',interfaceName:'Evidence-backed records workspace',purpose:'Authorized data matched to your request'};
}

export function intentPrimaryClaim(result: EnterpriseResponse): string | null {
  return result.claims.find(c=>c.kind==='observation'||c.kind==='calculation')?.text ||
    result.claims.find(c=>c.kind==='uncertainty')?.text || null;
}

export function intentWorkspaceLayers(result: EnterpriseResponse, functionalView: string | null): string[] {
  // A functional renderer takes the place of the v1 widget grid. Do not
  // advertise v1 widgets that are present in the payload but not mounted.
  const functionalLabels: Record<string,string[]> = {
    calendar:['Interactive weekly calendar'],workload:['Employee capacity chart'],usage:['Product usage analytics'],
    portfolio:['Executive portfolio dashboard'],incidents:['Severity-ranked incident board'],
    dependencies:['Task dependency visualizer','Actual versus expected progress chart'],
  };
  if (functionalView) return functionalLabels[functionalView] || [];
  return [...new Set(result.components.map(c=>c.title).filter(Boolean))].slice(0,4);
}
