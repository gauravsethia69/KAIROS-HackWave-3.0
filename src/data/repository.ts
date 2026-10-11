import { demoData } from './demo';
import type { Dataset } from './demo';
import { apiRequest } from '../lib/api';
import { workspacePlanSchema } from '../types/workspace';
import type { WorkspacePlan } from '../types/workspace';

export async function loadDataset(connected: boolean): Promise<Dataset> {
  if (!connected) return structuredClone(demoData);
  const [clients, projects, tasks, issues, communications] = await Promise.all([
    apiRequest<Dataset['clients']>('/api/clients'), apiRequest<Dataset['projects']>('/api/projects'),
    apiRequest<Dataset['tasks']>('/api/tasks'), apiRequest<Dataset['issues']>('/api/issues'), apiRequest<Dataset['communications']>('/api/communications'),
  ]);
  const details = await Promise.all(clients.map(async c => {
    const id = encodeURIComponent(c.id);
    const [meetings, usage] = await Promise.all([apiRequest<Dataset['meetings']>(`/api/clients/${id}/meetings`), apiRequest<Dataset['usage']>(`/api/clients/${id}/usage`)]);
    return { meetings, usage };
  }));
  return { clients, projects, tasks, issues, communications, meetings: details.flatMap(d => d.meetings), usage: details.flatMap(d => d.usage) };
}
export async function saveWorkspace(plan: WorkspacePlan) {
  const validated = workspacePlanSchema.parse(plan);
  await apiRequest('/api/workspace/sessions', { method: 'POST', body: JSON.stringify({ plan: validated }) });
}
export async function savedWorkspaces() {
  const data = await apiRequest<{ id: string; title: string; plan: unknown; created_at: string }[]>('/api/workspace/sessions');
  return data.map(row => ({ ...row, plan: workspacePlanSchema.parse(row.plan) }));
}
