import { z } from 'zod';

export const componentTypes = ['ClientProfile', 'MeetingBrief', 'UsageChart', 'MetricCards', 'ActivityTimeline', 'TaskList', 'ProjectProgress', 'IssuePanel', 'DataTable', 'InsightPanel'] as const;
export const selectors = ['clients', 'meetings', 'communications', 'usage', 'tasks', 'projects', 'issues', 'insights', 'activity'] as const;
export const bindings: Record<typeof componentTypes[number], readonly typeof selectors[number][]> = {
  ClientProfile: ['clients'], MeetingBrief: ['meetings'], UsageChart: ['usage'], MetricCards: ['usage'],
  ActivityTimeline: ['activity', 'communications', 'meetings'], TaskList: ['tasks'], ProjectProgress: ['projects'],
  IssuePanel: ['issues'], DataTable: ['usage', 'tasks', 'projects', 'issues', 'communications', 'meetings', 'clients'], InsightPanel: ['insights'],
};
export const widgetSchema = z.object({
  id: z.string().regex(/^[a-zA-Z0-9_-]+$/).max(64), type: z.enum(componentTypes),
  title: z.string().min(1).max(100), selector: z.enum(selectors),
  priority: z.number().int().min(1).max(10), size: z.enum(['small', 'medium', 'wide']),
  order: z.number().int().min(0).max(30), reason: z.string().min(1).max(500),
}).strict();
export const workspacePlanSchema = z.object({
  schemaVersion: z.literal(1), intent: z.enum(['overview', 'meeting', 'usage', 'projects']),
  title: z.string().min(1).max(140), selectedEntityIds: z.array(z.enum(['acme', 'nova'])).max(2),
  filters: z.object({ days: z.union([z.literal(7), z.literal(14), z.literal(30)]), unresolvedOnly: z.boolean(), compare: z.boolean() }).strict(),
  layout: z.array(widgetSchema).min(1).max(12),
  explanations: z.array(z.string().max(500)).min(1).max(16),
  clarification: z.object({ question: z.string().min(1).max(300), options: z.array(z.string().min(1).max(160)).min(2).max(4) }).strict().optional(),
}).strict().superRefine((plan, ctx) => {
  if (new Set(plan.layout.map(w => w.id)).size !== plan.layout.length) ctx.addIssue({ code: 'custom', message: 'Instance IDs must be unique', path: ['layout'] });
  for (const [i, widget] of plan.layout.entries()) if (!bindings[widget.type].includes(widget.selector)) ctx.addIssue({ code: 'custom', message: 'Component cannot bind this selector', path: ['layout', i, 'selector'] });
});
export type WorkspacePlan = z.infer<typeof workspacePlanSchema>;
export type WidgetPlan = z.infer<typeof widgetSchema>;
