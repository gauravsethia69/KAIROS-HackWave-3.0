import catalog from './capabilities.json';
import { workspacePlanSchema } from '../types/workspace';
import type { WorkspacePlan, WidgetPlan } from '../types/workspace';

type Intent = WorkspacePlan['intent'];
// A reusable capability catalog, scored by goal. No per-scenario dashboard markup.
const capabilities = catalog as { type: WidgetPlan['type']; selector: WidgetPlan['selector']; title: string; weights: Record<Intent, number>; reason: string }[];
export function classifyIntent(input: string): Intent | null {
  const q = input.toLowerCase();
  if (/project|behind|schedule|deadline|overdue|delivery/.test(q) && !/meeting|training/.test(q)) return 'projects';
  if (/usage|adoption|active users|engagement|product activity|drop|declin/.test(q)) return 'usage';
  if (/meeting|brief|prepare|catch.?up|client call|review with|talk to/.test(q)) return 'meeting';
  if (/overview|dashboard|start over|home/.test(q)) return 'overview';
  return null;
}
export function compose(intent: Intent, entities: WorkspacePlan['selectedEntityIds'] = [], filters = { days: 30 as 7 | 14 | 30, unresolvedOnly: false, compare: false }): WorkspacePlan {
  const names = entities.map(id => id === 'acme' ? 'Acme Corp' : 'Nova Studio').join(' & ');
  const titles = { overview: 'A little clarity. A lot of possibility.', meeting: `Ready for your next conversation${names ? ` with ${names}` : ''}`, usage: `Understand what changed${names ? ` at ${names}` : ''}`, projects: `Bring delivery back on track${names ? ` · ${names}` : ''}` };
  const layout = capabilities.filter(c => c.weights[intent] > 0).sort((a, b) => b.weights[intent] - a.weights[intent]).map((c, i): WidgetPlan => ({
    id: `${c.type}-${c.selector}`, type: c.type, selector: c.selector, title: intent === 'overview' && c.type === 'ProjectProgress' ? 'Project portfolio' : c.title, priority: c.weights[intent],
    order: i, size: c.type === 'MetricCards' ? 'wide' : i === 0 ? 'wide' : c.type === 'ClientProfile' ? 'small' : 'medium', reason: c.reason,
  }));
  return workspacePlanSchema.parse({ schemaVersion: 1, intent, title: titles[intent], selectedEntityIds: entities, filters, layout, explanations: [`Recognized goal: ${intent === 'overview' ? 'general workspace overview' : intent === 'meeting' ? 'prepare a client meeting' : intent === 'usage' ? 'investigate product usage' : 'review delivery risks'}.`, `Scope: ${names || 'all available clients'}. Widgets are ranked by relevance to this goal.`] });
}
export const initialPlan = () => compose('overview');
function clarify(previous: WorkspacePlan, question: string, options: string[]): WorkspacePlan {
  return workspacePlanSchema.parse({ ...previous, clarification: { question, options } });
}
export function transform(input: string, previous: WorkspacePlan): WorkspacePlan | null {
  const q = input.toLowerCase().trim();
  const next: WorkspacePlan = structuredClone(previous);
  delete next.clarification;
  let change = '';
  if (/last\s+\d+\s+days?/.test(q)) {
    const days = Number(q.match(/last\s+(\d+)\s+days?/)?.[1]);
    if (![7, 14, 30].includes(days)) return clarify(previous, 'Choose an available date window.', ['Show only the last 7 days', 'Show only the last 14 days', 'Show only the last 30 days']);
    next.filters.days = days as 7 | 14 | 30; change = `Date window changed to the last ${days} days; client and goal retained.`;
  } else if (/\b(move|put|bring)\b.*\b(chart|graph)\b.*\b(top|first)\b/.test(q)) {
    const chart = next.layout.find(w => w.type === 'UsageChart');
    if (!chart) return clarify(previous, 'There is no usage chart in this workspace. Which client should we investigate?', ['Investigate Acme Corp usage', 'Investigate Nova Studio usage']);
    next.layout = [chart, ...next.layout.filter(w => w.id !== chart.id)].map((w, i) => ({ ...w, order: i, size: i === 0 ? 'wide' : w.size })); change = 'Product adoption moved to the top of the workspace.';
  } else if (/\btable\b/.test(q)) {
    const target = /issues?/.test(q) ? 'issues' : /tasks?/.test(q) ? 'tasks' : /project/.test(q) ? 'projects' : /usage|chart/.test(q) ? 'usage' : next.intent === 'usage' ? 'usage' : next.intent === 'projects' ? 'projects' : null;
    if (!target) return clarify(previous, 'Which information would you like as a table?', ['Show issues as a table', 'Show tasks as a table', 'Show usage as a table']);
    const widget = next.layout.find(w => w.selector === target && w.type !== 'MetricCards');
    if (!widget) return clarify(previous, 'That data is not in this workspace. Choose a goal first.', ['Investigate Acme Corp usage', 'Review projects falling behind schedule']);
    widget.type = 'DataTable'; widget.title = `${target[0].toUpperCase()}${target.slice(1)} · table`; widget.size = 'wide'; widget.reason = `The same ${target} records are shown in a table at your request.`; change = `Changed ${target} to a table; filters and entity selection retained.`;
  } else if (/unresolved|open issues/.test(q)) {
    next.filters.unresolvedOnly = true;
    const existing = next.layout.find(w => w.selector === 'issues');
    const issue: WidgetPlan = existing || { id: 'IssuePanel-issues', type: 'IssuePanel', title: 'Unresolved issues', selector: 'issues', priority: 10, order: 0, size: 'wide', reason: 'You asked to focus on unresolved issues.' };
    next.layout = [{ ...issue, size: 'wide' as const }, ...next.layout.filter(w => w.id !== issue.id)].map((w, i) => ({ ...w, order: i })); change = 'Resolved issues hidden; unresolved issues prioritized.';
  } else if (/compare|previous period/.test(q)) {
    if (!next.layout.some(w => w.selector === 'usage')) return clarify(previous, 'Period comparison is available for usage. Choose a client.', ['Investigate Acme Corp usage', 'Investigate Nova Studio usage']);
    next.filters.compare = true; change = `Added the preceding ${next.filters.days}-day period for comparison.`;
  } else if (/reset filters|clear filters/.test(q)) {
    next.filters = { days: 30, unresolvedOnly: false, compare: false }; change = 'Filters reset; goal and client retained.';
  } else return null;
  next.explanations = [previous.explanations[0], change];
  return workspacePlanSchema.parse(next);
}
export function planLocally(input: string, previous: WorkspacePlan = initialPlan()): WorkspacePlan {
  if (input.length > 2000) return clarify(previous, 'Please shorten your request to 2,000 characters.', ['Prepare for Acme Corp meeting', 'Investigate Acme Corp usage']);
  const q = input.toLowerCase();
  const mentioned = (['acme', 'nova'] as const).filter(id => q.includes(id));
  const intent = classifyIntent(input);
  // Explicit goal changes win over follow-up keywords; simple transforms retain scope.
  const isGoal = /investigate|prepare|review projects|why .*drop|why .*declin/.test(q);
  if (!isGoal && !mentioned.length) { const transformed = transform(input, previous); if (transformed) return transformed; }
  if (!intent && previous.clarification && mentioned.length) {
    const pending = previous.clarification.options.find(o => o.toLowerCase().includes(mentioned[0]));
    if (pending) return planLocally(pending, { ...previous, clarification: undefined });
  }
  if (!intent && mentioned.length && previous.intent !== 'overview' && !/compare/.test(q)) {
    const next = compose(previous.intent, mentioned, { ...previous.filters });
    next.explanations.push('Client selection changed; the current goal and filters were retained.');
    return next;
  }
  if (!intent) return clarify(previous, 'What would you like to accomplish?', ['Prepare for an Acme Corp meeting', 'Investigate Acme Corp usage', 'Review projects falling behind schedule']);
  if (intent === 'overview') return initialPlan();
  if (!mentioned.length && /\b(?:with|at)\s+(?!the\b|my\b|our\b)[a-z]/.test(q)) return clarify(previous, 'Only Acme Corp and Nova Studio are available in this dataset. Which client should I use?', intent === 'meeting' ? ['Prepare for Acme Corp meeting', 'Prepare for Nova Studio meeting'] : ['Investigate Acme Corp usage', 'Investigate Nova Studio usage']);
  if (mentioned.length > 1 && intent === 'meeting') return clarify(previous, 'Which client meeting should I prepare?', ['Prepare for Acme Corp meeting', 'Prepare for Nova Studio meeting']);
  const entities = mentioned.length ? mentioned : intent === 'projects' ? [] : previous.selectedEntityIds;
  if ((intent === 'meeting' || intent === 'usage') && !entities.length) return clarify(previous, 'Which client should this workspace focus on?', intent === 'meeting' ? ['Prepare for Acme Corp meeting', 'Prepare for Nova Studio meeting'] : ['Investigate Acme Corp usage', 'Investigate Nova Studio usage']);
  const next = compose(intent, entities, { ...previous.filters });
  next.explanations.push(`Workspace recomposed from ${previous.intent} to ${intent}; ${next.layout.length} relevant widgets selected.`);
  return next;
}
