import { DEMO_DATE } from './demo';
import type { Dataset } from './demo';
import type { WorkspacePlan, WidgetPlan } from '../types/workspace';

export function daysAgo(days: number) { const d = new Date(`${DEMO_DATE}T00:00:00Z`); d.setUTCDate(d.getUTCDate() - days); return d.toISOString().slice(0, 10); }
export function scopeData(data: Dataset, plan: WorkspacePlan): Dataset {
  const ids = plan.selectedEntityIds;
  const selected = <T extends { client_id: string }>(rows: T[]) => rows.filter(r => !ids.length || ids.includes(r.client_id as 'acme' | 'nova'));
  const projects = selected(data.projects).filter(p => plan.intent !== 'projects' || p.progress < p.expected);
  const projectIds = new Set(projects.map(p => p.id));
  return {
    clients: data.clients.filter(c => !ids.length || ids.includes(c.id as 'acme' | 'nova')),
    meetings: selected(data.meetings).filter(m => m.upcoming || m.date >= daysAgo(plan.filters.days - 1)),
    communications: selected(data.communications).filter(c => c.date >= daysAgo(plan.filters.days - 1) && c.date <= DEMO_DATE),
    usage: selected(data.usage).filter(u => u.date >= daysAgo(plan.filters.days * 2 - 1) && u.date <= DEMO_DATE),
    projects,
    tasks: selected(data.tasks).filter(t => (plan.intent !== 'projects' || projectIds.has(t.project_id)) && t.status !== 'Done'),
    issues: selected(data.issues).filter(i => (plan.intent !== 'projects' || projectIds.has(i.project_id)) && (!plan.filters.unresolvedOnly || i.status !== 'Resolved') && i.date >= daysAgo(plan.filters.days - 1) && i.date <= DEMO_DATE),
  };
}
export function usageSeries(data: Dataset, plan: WorkspacePlan) {
  const sums = new Map<string, { date: string; active_users: number; sessions: number; errors: number }>();
  for (const row of data.usage) { const sum = sums.get(row.date) || { date: row.date, active_users: 0, sessions: 0, errors: 0 }; sum.active_users += row.active_users; sum.sessions += row.sessions; sum.errors += row.errors; sums.set(row.date, sum); }
  return Array.from({ length: plan.filters.days }, (_, i) => {
    const date = daysAgo(plan.filters.days - 1 - i);
    const current = sums.get(date);
    const prior = sums.get(daysAgo(plan.filters.days * 2 - 1 - i));
    return { date, label: date.slice(5), active_users: current?.active_users ?? null, sessions: current?.sessions ?? null, errors: current?.errors ?? null, previous: prior?.active_users ?? null };
  });
}
export function metrics(data: Dataset, plan: WorkspacePlan) {
  const rows = usageSeries(data, plan);
  const valid = rows.filter(r => r.active_users !== null);
  const prev = rows.filter(r => r.previous !== null);
  const average = valid.length ? valid.reduce((s, r) => s + (r.active_users || 0), 0) / valid.length : 0;
  const previous = prev.length ? prev.reduce((s, r) => s + (r.previous || 0), 0) / prev.length : 0;
  return { average: Math.round(average), change: previous ? Math.round((average - previous) / previous * 100) : null, sessions: valid.reduce((s, r) => s + (r.sessions || 0), 0), errors: valid.reduce((s, r) => s + (r.errors || 0), 0), count: valid.length };
}
export interface Insight { kind: 'Observation' | 'Hypothesis' | 'Action'; text: string; source: string }
export function insights(data: Dataset, plan: WorkspacePlan): Insight[] {
  const out: Insight[] = [];
  if (plan.intent === 'usage') {
    const m = metrics(data, plan);
    if (m.count) out.push({ kind: 'Observation', text: `Average daily active users: ${m.average}${m.change === null ? '' : ` (${m.change > 0 ? '+' : ''}${m.change}% versus the preceding period)`}. ${m.errors} errors recorded.`, source: `product_usage · ${m.count} daily observations` });
    const sso = data.issues.find(i => i.id === 'i1');
    if (sso) out.push({ kind: 'Hypothesis', text: 'SSO failures may be contributing to reduced adoption. Timing overlaps; these records do not establish causation.', source: `${sso.id} · ${sso.title} · ${sso.date}` });
    const training = data.communications.find(c => c.id === 'c3');
    if (training) out.push({ kind: 'Hypothesis', text: 'Postponed operator training may be limiting engagement. Validate with the affected cohort.', source: `${training.id} · ${training.author} · ${training.date}` });
    if (m.count) out.push({ kind: 'Action', text: 'Compare affected and unaffected user cohorts, then check adoption after the fix before attributing a cause.', source: 'Suggested investigation; not a confirmed finding' });
  } else if (plan.intent === 'projects') {
    for (const p of data.projects) out.push({ kind: 'Observation', text: `${p.name} is ${p.expected - p.progress} percentage points behind expected progress. Owner: ${p.owner}.`, source: `${p.id} · projects · due ${p.due_date}` });
  } else {
    for (const issue of data.issues.filter(i => i.status !== 'Resolved').slice(0, 3)) out.push({ kind: 'Action', text: `Confirm a resolution plan for ${issue.title.toLowerCase()} with ${issue.owner}.`, source: `${issue.id} · issues · ${issue.date}` });
  }
  return out;
}
export function tableRows(data: Dataset, plan: WorkspacePlan, selector: WidgetPlan['selector']): Record<string, unknown>[] {
  switch (selector) {
    case 'usage': return usageSeries(data, plan).filter(r => r.active_users !== null).map(r => ({ Date: r.date, 'Active users': r.active_users, Sessions: r.sessions, Errors: r.errors, ...(plan.filters.compare ? { 'Previous period users': r.previous } : {}) }));
    case 'projects': return data.projects.map(p => ({ Project: p.name, Owner: p.owner, Progress: `${p.progress}%`, Expected: `${p.expected}%`, Due: p.due_date, Status: p.status }));
    case 'tasks': return data.tasks.map(t => ({ Task: t.title, Owner: t.owner, Due: t.due_date, Status: t.status }));
    case 'issues': return data.issues.map(i => ({ Issue: i.title, Owner: i.owner, Severity: i.severity, Status: i.status }));
    case 'meetings': return data.meetings.map(m => ({ Meeting: m.title, Date: m.date, Summary: m.summary }));
    case 'communications': return data.communications.map(c => ({ Date: c.date, Author: c.author, Message: c.message }));
    case 'clients': return data.clients.map(c => ({ Client: c.name, Contact: c.contact, Owner: c.owner, Health: c.health }));
    default: return [];
  }
}
