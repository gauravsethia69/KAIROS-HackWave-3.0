export const DEMO_DATE = '2026-10-10';
export interface Client { id: string; name: string; sector: string; contact: string; email: string; owner: string; plan: string; seats: number; health: string }
export interface Meeting { id: string; client_id: string; title: string; date: string; summary: string; attendees: string; upcoming: boolean }
export interface Communication { id: string; client_id: string; date: string; author: string; channel: string; message: string }
export interface Usage { id: string; client_id: string; date: string; active_users: number; sessions: number; errors: number }
export interface Project { id: string; client_id: string; name: string; owner: string; progress: number; expected: number; due_date: string; status: string }
export interface Task { id: string; client_id: string; project_id: string; title: string; owner: string; due_date: string; status: string; priority: string }
export interface Issue { id: string; client_id: string; project_id: string; title: string; date: string; status: string; severity: string; owner: string; detail: string }
export interface Dataset { activity?: { id: string; date: string; title: string; text: string; label: string }[]; clients: Client[]; meetings: Meeting[]; communications: Communication[]; usage: Usage[]; projects: Project[]; tasks: Task[]; issues: Issue[] }
export const demoData: Dataset = {
  clients: [
    { id: 'acme', name: 'Acme Corp', sector: 'Enterprise logistics', contact: 'Maya Chen', email: 'maya@acme.example', owner: 'Alex Morgan', plan: 'Enterprise', seats: 180, health: 'Needs attention' },
    { id: 'nova', name: 'Nova Studio', sector: 'Design & collaboration', contact: 'Theo Park', email: 'theo@nova.example', owner: 'Priya Shah', plan: 'Growth', seats: 65, health: 'Healthy' },
  ],
  meetings: [
    { id: 'm1', client_id: 'acme', title: 'Quarterly success review', date: '2026-10-11', summary: 'Review adoption, resolve SSO concerns, and agree on the rollout recovery plan.', attendees: 'Maya Chen · Alex Morgan · Jordan Lee', upcoming: true },
    { id: 'm2', client_id: 'acme', title: 'Platform rollout checkpoint', date: '2026-10-03', summary: 'Maya reported login friction. Agreed to validate SSO and train the operations team before expanding.', attendees: 'Maya Chen · Jordan Lee', upcoming: false },
    { id: 'm3', client_id: 'acme', title: 'Adoption & enablement', date: '2026-09-25', summary: 'Training postponed due to shift changes. Acme requested a recorded walkthrough.', attendees: 'Maya Chen · Alex Morgan', upcoming: false },
    { id: 'm4', client_id: 'nova', title: 'Creative operations sync', date: '2026-10-12', summary: 'Confirm asset migration and review feedback on the new shared library.', attendees: 'Theo Park · Priya Shah', upcoming: true },
  ],
  communications: [
    { id: 'c1', client_id: 'acme', date: '2026-10-09', author: 'Maya Chen', channel: 'Email', message: 'Several operators still cannot sign in with SSO. Please bring a recovery timeline to our review.' },
    { id: 'c2', client_id: 'acme', date: '2026-10-07', author: 'Jordan Lee', channel: 'Support', message: 'SSO callback failures reproduced on the new identity provider. A fix is in validation.' },
    { id: 'c3', client_id: 'acme', date: '2026-10-04', author: 'Maya Chen', channel: 'Email', message: 'Operations training remains on hold until the new shift schedule is approved.' },
    { id: 'c4', client_id: 'nova', date: '2026-10-08', author: 'Theo Park', channel: 'Email', message: 'The asset library pilot is going well. Waiting on final legal approval for migration.' },
  ],
  usage: Array.from({ length: 60 }, (_, i) => {
    const date = new Date(Date.UTC(2026, 9, 10 - (59 - i))).toISOString().slice(0, 10);
    return ['acme', 'nova'].map((client_id, j) => {
      const drop = client_id === 'acme' && date >= '2026-10-01';
      const active_users = j ? 42 + i % 7 : (drop ? 68 : 132) + (i * 7 % 13);
      return { id: `u${i}-${j}`, client_id, date, active_users, sessions: active_users * (drop ? 3 : 5), errors: drop ? 24 + i % 9 : 2 + i % 3 };
    });
  }).flat(),
  projects: [
    { id: 'p1', client_id: 'acme', name: 'Operations rollout', owner: 'Jordan Lee', progress: 58, expected: 85, due_date: '2026-10-14', status: 'At risk' },
    { id: 'p2', client_id: 'acme', name: 'Analytics integration', owner: 'Sam Rivera', progress: 42, expected: 75, due_date: '2026-10-08', status: 'Delayed' },
    { id: 'p3', client_id: 'nova', name: 'Asset library migration', owner: 'Priya Shah', progress: 71, expected: 90, due_date: '2026-10-13', status: 'At risk' },
    { id: 'p4', client_id: 'nova', name: 'Workspace onboarding', owner: 'Theo Park', progress: 92, expected: 90, due_date: '2026-10-18', status: 'On track' },
  ],
  tasks: [
    { id: 't1', client_id: 'acme', project_id: 'p1', title: 'Validate SSO callback fix', owner: 'Jordan Lee', due_date: '2026-10-09', status: 'Blocked', priority: 'High' },
    { id: 't2', client_id: 'acme', project_id: 'p1', title: 'Reschedule operator training', owner: 'Alex Morgan', due_date: '2026-10-07', status: 'Open', priority: 'High' },
    { id: 't3', client_id: 'acme', project_id: 'p2', title: 'Approve event mapping contract', owner: 'Sam Rivera', due_date: '2026-10-06', status: 'Blocked', priority: 'High' },
    { id: 't4', client_id: 'nova', project_id: 'p3', title: 'Obtain asset licensing approval', owner: 'Priya Shah', due_date: '2026-10-09', status: 'Open', priority: 'Medium' },
    { id: 't5', client_id: 'acme', project_id: 'p1', title: 'Publish recorded walkthrough', owner: 'Alex Morgan', due_date: '2026-10-12', status: 'Open', priority: 'Medium' },
    { id: 't6', client_id: 'nova', project_id: 'p4', title: 'Complete workspace orientation', owner: 'Theo Park', due_date: '2026-10-08', status: 'Done', priority: 'Low' },
  ],
  issues: [
    { id: 'i1', client_id: 'acme', project_id: 'p1', title: 'SSO callback failures', date: '2026-10-01', status: 'Investigating', severity: 'High', owner: 'Jordan Lee', detail: 'Failures began after identity-provider migration. Support reproduced the issue; the impact on adoption is not yet isolated.' },
    { id: 'i2', client_id: 'acme', project_id: 'p1', title: 'Training delayed', date: '2026-10-04', status: 'Open', severity: 'Medium', owner: 'Alex Morgan', detail: 'Operations shift changes postponed enablement. Confirm a replacement session with Maya.' },
    { id: 'i3', client_id: 'acme', project_id: 'p2', title: 'Event contract awaiting approval', date: '2026-10-05', status: 'Open', severity: 'High', owner: 'Sam Rivera', detail: 'Analytics integration is blocked until the client approves the event mapping contract.' },
    { id: 'i4', client_id: 'nova', project_id: 'p3', title: 'Asset licensing review', date: '2026-10-06', status: 'Open', severity: 'Medium', owner: 'Priya Shah', detail: 'Legal review is holding the final migration batch.' },
    { id: 'i5', client_id: 'acme', project_id: 'p1', title: 'Export timezone mismatch', date: '2026-09-28', status: 'Resolved', severity: 'Low', owner: 'Jordan Lee', detail: 'Timezone normalization shipped and verified on September 30.' },
  ],
};
