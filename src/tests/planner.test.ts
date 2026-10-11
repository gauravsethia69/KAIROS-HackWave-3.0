import { describe, expect, it } from 'vitest';
import { classifyIntent, initialPlan, planLocally } from '../ai/planner';
import { workspacePlanSchema } from '../types/workspace';
import { demoData } from '../data/demo';
import { insights, metrics, scopeData, tableRows, usageSeries } from '../data/selectors';

describe('intent interpretation', () => {
  it.each([
    ['Prepare me for tomorrow\'s client meeting with Acme Corp.', 'meeting'],
    ['Brief me before my client call with Acme', 'meeting'],
    ['Help me get ready for a catch-up with Nova', 'meeting'],
    ["Investigate why Acme Corp's product usage dropped.", 'usage'],
    ['Why is engagement declining at Acme?', 'usage'],
    ['Show active users for Nova', 'usage'],
    ['Review projects that are falling behind schedule.', 'projects'],
    ['Which delivery deadlines are at risk?', 'projects'],
    ['Show overdue work', 'projects'],
  ])('classifies %s', (input, intent) => expect(classifyIntent(input)).toBe(intent));
  it('asks for an ambiguous client without replacing the workspace', () => {
    const previous = initialPlan(); const next = planLocally('Prepare for a client meeting', previous);
    expect(next.clarification?.options).toHaveLength(2); expect(next.layout).toEqual(previous.layout);
    const answered = planLocally('Acme', next); expect(answered.intent).toBe('meeting'); expect(answered.selectedEntityIds).toEqual(['acme']); expect(answered.clarification).toBeUndefined();
  });
  it('asks about an unknown goal', () => expect(planLocally('Help me with this thing').clarification).toBeDefined());
  it('asks about competing meeting clients', () => expect(planLocally('Meeting with Acme and Nova').clarification).toBeDefined());
  it('does not reuse Acme when an unavailable client is explicitly requested', () => expect(planLocally('Prepare for a meeting with Globex', planLocally('Prepare for Acme meeting')).clarification).toBeDefined());
  it('accepts a client-only follow-up without losing the goal', () => { const next = planLocally('Focus on Nova', planLocally('Investigate Acme usage')); expect(next.intent).toBe('usage'); expect(next.selectedEntityIds).toEqual(['nova']); });
});
describe('schema safety', () => {
  it('validates a composed plan', () => expect(workspacePlanSchema.safeParse(initialPlan()).success).toBe(true));
  it.each(['Script', '<script>', 'iframe'])('rejects unknown component %s', type => { const plan = initialPlan(); expect(workspacePlanSchema.safeParse({ ...plan, layout: [{ ...plan.layout[0], type }] }).success).toBe(false); });
  it('rejects unauthorized selectors', () => { const plan = initialPlan(); expect(workspacePlanSchema.safeParse({ ...plan, layout: [{ ...plan.layout[0], selector: 'auth.users' }] }).success).toBe(false); });
  it('rejects incompatible component bindings', () => { const plan = initialPlan(); expect(workspacePlanSchema.safeParse({ ...plan, layout: [{ ...plan.layout[0], type: 'UsageChart', selector: 'clients' }] }).success).toBe(false); });
  it('rejects duplicate instances', () => { const plan = initialPlan(); expect(workspacePlanSchema.safeParse({ ...plan, layout: [plan.layout[0], plan.layout[0]] }).success).toBe(false); });
  it('rejects executable extra properties', () => expect(workspacePlanSchema.safeParse({ ...initialPlan(), html: '<script>alert(1)</script>' }).success).toBe(false));
  it('rejects unknown clients and unsupported windows', () => { expect(workspacePlanSchema.safeParse({ ...initialPlan(), selectedEntityIds: ['private-client'] }).success).toBe(false); expect(workspacePlanSchema.safeParse({ ...initialPlan(), filters: { days: 365, compare: false, unresolvedOnly: false } }).success).toBe(false); });
});
describe('required demonstrations', () => {
  it('prepares a meeting with profile, brief, records, communications, issues and actions', () => {
    const plan = planLocally("Prepare me for tomorrow's client meeting with Acme Corp.");
    const scoped = scopeData(demoData, plan);
    expect(plan.intent).toBe('meeting'); expect(plan.selectedEntityIds).toEqual(['acme']);
    expect(plan.layout.map(w => w.type)).toEqual(expect.arrayContaining(['ClientProfile','MeetingBrief','ActivityTimeline','IssuePanel','TaskList','InsightPanel']));
    expect(scoped.meetings.some(m => m.date === '2026-10-11' && m.upcoming)).toBe(true);
    expect(scoped.meetings.some(m => !m.upcoming)).toBe(true); expect(scoped.communications.length).toBeGreaterThan(0);
  });
  it('investigates usage with measurable decline and explicitly hypothetical causes', () => {
    const plan = planLocally("Investigate why Acme Corp's product usage dropped."); const scoped = scopeData(demoData, plan);
    expect(plan.layout[0].type).toBe('UsageChart'); expect(metrics(scoped, plan).change).toBeLessThan(0);
    expect(insights(scoped, plan).map(i => i.kind)).toEqual(expect.arrayContaining(['Observation','Hypothesis','Action']));
    expect(insights(scoped, plan).every(i => i.source.length > 0)).toBe(true);
  });
  it('reviews late projects across clients and excludes on-track work', () => {
    const previous = planLocally('Prepare for Acme meeting'); const plan = planLocally('Review projects that are falling behind schedule.', previous); const scoped = scopeData(demoData, plan);
    expect(plan.selectedEntityIds).toEqual([]); expect(plan.layout[0].type).toBe('ProjectProgress');
    expect(scoped.projects.map(p => p.id)).toEqual(['p1','p2','p3']); expect(scoped.tasks.some(t => t.project_id === 'p4')).toBe(false);
  });
  it('keeps Nova evidence separate from Acme evidence', () => { const plan = planLocally('Investigate Nova usage'); const scoped = scopeData(demoData, plan); expect(scoped.issues.every(i => i.client_id === 'nova')).toBe(true); expect(insights(scoped, plan).some(i => i.text.includes('SSO'))).toBe(false); });
});
describe('follow-up adaptation', () => {
  const usage = planLocally('Investigate Acme product usage');
  it('preserves the entity and goal while applying date filters', () => { const plan = planLocally('Show only the last 14 days.', usage); expect(plan.selectedEntityIds).toEqual(['acme']); expect(plan.intent).toBe('usage'); expect(plan.filters.days).toBe(14); expect(usageSeries(scopeData(demoData, plan), plan)).toHaveLength(14); });
  it('moves a chart to the top', () => { const shuffled = { ...usage, layout: [...usage.layout].reverse().map((w, i) => ({ ...w, order: i })) }; const plan = planLocally('Move the usage chart to the top.', shuffled); expect(plan.layout[0].type).toBe('UsageChart'); expect(plan.layout[0].order).toBe(0); expect(plan.layout[0].size).toBe('wide'); });
  it('replaces chart with the same data as a table', () => { const plan = planLocally('Show this information as a table instead.', usage); expect(plan.layout.some(w => w.type === 'UsageChart')).toBe(false); expect(plan.layout.find(w => w.type === 'DataTable')?.selector).toBe('usage'); expect(tableRows(scopeData(demoData, plan), plan, 'usage')).toHaveLength(30); });
  it('prioritizes unresolved issues', () => { const plan = planLocally('Focus on unresolved issues.', usage); expect(plan.layout[0].selector).toBe('issues'); expect(scopeData(demoData, plan).issues.every(i => i.status !== 'Resolved')).toBe(true); });
  it('adds correctly aligned prior-period records', () => { const plan = planLocally('Compare this with the previous period.', planLocally('Show only the last 14 days.', usage)); const series = usageSeries(scopeData(demoData, plan), plan); expect(plan.filters.compare).toBe(true); expect(series.every(r => r.previous !== null)).toBe(true); const prior = demoData.usage.find(u => u.client_id === 'acme' && u.date === '2026-09-13'); expect(series[0].previous).toBe(prior?.active_users); });
  it('preserves client when changing from meeting to usage', () => expect(planLocally('Investigate the usage drop', planLocally('Prepare for Nova meeting')).selectedEntityIds).toEqual(['nova']));
  it('asks which table for an ambiguous meeting request', () => expect(planLocally('Show this as a table', planLocally('Prepare for Acme meeting')).clarification).toBeDefined());
  it('asks for a supported window', () => expect(planLocally('Show only the last 90 days', usage).clarification).toBeDefined());
  it('does not fabricate missing usage measurements', () => { const data = scopeData({ ...demoData, usage: [] }, usage); expect(metrics(data, usage).count).toBe(0); expect(usageSeries(data, usage).every(r => r.active_users === null)).toBe(true); });
});
