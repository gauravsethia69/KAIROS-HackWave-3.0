import { useState } from 'react';
import type { ComponentType } from 'react';
import { ArrowUpRight, CalendarDays, Check, CheckCircle2, ChevronDown, Circle, Download, Mail, TriangleAlert } from 'lucide-react';
import { Area, CartesianGrid, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Dataset } from '../../data/demo';
import { DEMO_DATE } from '../../data/demo';
import { insights, metrics, tableRows, usageSeries } from '../../data/selectors';
import type { WorkspacePlan, WidgetPlan } from '../../types/workspace';
export interface WidgetProps { data: Dataset; plan: WorkspacePlan; widget: WidgetPlan; completed: Set<string>; onToggleTask: (id: string) => void; onIntent: (input: string) => void }
export function Empty({ message = 'No matching records in this scope.' }: { message?: string }) { return <div className="empty"><Circle size={22}/><p>{message}</p><span>Try another client or reset your filters.</span></div>; }
function ClientProfile({ data, onIntent }: WidgetProps) {
  if (!data.clients.length) return <Empty/>;
  return <div className="client-list">{data.clients.map(c => <div key={c.id}><div className="client-heading"><span className="avatar">{c.name.slice(0, 1)}</span><div><h3>{c.name}</h3><p>{c.sector}</p></div></div><span className={`badge ${c.health === 'Healthy' ? 'green' : 'pink'}`}>{c.health}</span><dl><div><dt>Primary contact</dt><dd>{c.contact}</dd></div><div><dt>Account owner</dt><dd>{c.owner}</dd></div><div><dt>Plan / seats</dt><dd>{c.plan} · {c.seats}</dd></div></dl><button className="text-button" onClick={() => onIntent(`Investigate ${c.name} usage`)}>Explore adoption <ArrowUpRight size={14}/></button></div>)}</div>;
}
function MeetingBrief({ data }: WidgetProps) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const meetings = data.meetings.filter(m => m.upcoming);
  if (!meetings.length) return <Empty message="No upcoming meeting is scheduled for this client."/>;
  async function copy() { try { await navigator.clipboard.writeText(meetings.map(m => `${m.title}\n${m.date}\n${m.attendees}\n${m.summary}`).join('\n\n')); setCopied(true); setCopyError(false); } catch { setCopyError(true); } }
  return <div className="meeting-brief">{meetings.map(m => <div key={m.id}><span className="eyebrow cyan"><CalendarDays size={13}/> {m.date} · DEMO CALENDAR</span><h3>{m.title}</h3><p>{m.summary}</p><div className="attendees">{m.attendees.split(' · ').map(a => <span key={a}><span className="avatar tiny">{a.split(' ').map(n => n[0]).join('')}</span>{a}</span>)}</div></div>)}<button className="secondary" onClick={copy}>{copied ? <Check size={14}/> : <Mail size={14}/>} {copied ? 'Brief copied' : 'Copy meeting brief'}</button>{copyError && <p role="alert">Clipboard unavailable. Select and copy the brief above.</p>}</div>;
}
function UsageChart({ data, plan }: WidgetProps) {
  const series = usageSeries(data, plan);
  if (!series.some(r => r.active_users !== null)) return <Empty message="No usage measurements for this period."/>;
  return <><div className="chart-legend"><span><i/> Daily active users</span>{plan.filters.compare && <span><i className="previous"/> Previous {plan.filters.days} days</span>}<span className="muted">{plan.filters.days}-day window</span></div><div className="chart" role="img" aria-label="Daily active user trend. Use Show as table for the accessible data values."><ResponsiveContainer width="100%" height="100%"><ComposedChart data={series} margin={{ top: 18, right: 10, bottom: 0, left: -22 }}><defs><linearGradient id="usageFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#73d9ed" stopOpacity={0.24}/><stop offset="100%" stopColor="#73d9ed" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#2c343e" strokeDasharray="3 5"/><XAxis dataKey="label" tick={{ fill: '#9ba7b6', fontSize: 11 }} minTickGap={35} axisLine={false} tickLine={false}/><YAxis tick={{ fill: '#9ba7b6', fontSize: 11 }} axisLine={false} tickLine={false}/><Tooltip contentStyle={{ background: '#19212b', border: '1px solid #475465', borderRadius: 10 }} labelStyle={{ color: '#f6f0e6' }}/><Area type="monotone" dataKey="active_users" name="Daily active users" stroke="#73d9ed" fill="url(#usageFill)" strokeWidth={2.5}/>{plan.filters.compare && <Line type="monotone" dataKey="previous" name="Previous period" stroke="#f5a9bf" dot={false} strokeDasharray="5 5" strokeWidth={2}/>}</ComposedChart></ResponsiveContainer></div><p className="footnote">Source: daily product usage · missing measurements are gaps, not zeroes.</p></>;
}
function MetricCards({ data, plan }: WidgetProps) {
  const m = metrics(data, plan);
  if (!m.count) return <Empty/>;
  return <div className="metric-grid"><div><span>AVG. DAILY ACTIVE USERS</span><strong>{m.average}<small className={m.change !== null && m.change < 0 ? 'pink-text' : 'cyan'}>{m.change === null ? 'No baseline' : `${m.change > 0 ? '+' : ''}${m.change}%`}</small></strong><p>vs. preceding {plan.filters.days} days</p></div><div><span>TOTAL SESSIONS</span><strong>{m.sessions.toLocaleString()}</strong><p>Across {m.count} measured days</p></div><div><span>RECORDED ERRORS</span><strong>{m.errors.toLocaleString()}</strong><p>Investigate before attributing cause</p></div></div>;
}
function ActivityTimeline({ data, widget }: WidgetProps) {
  const rows = widget.selector === 'activity' && data.activity
    ? data.activity.map(item => ({...item}))
    : widget.selector === 'meetings'
      ? data.meetings.filter(m => !m.upcoming).map(m => ({ id: m.id, date: m.date, title: m.title, text: m.summary, label: 'Meeting' }))
      : [
          ...data.communications.map(c => ({ id: c.id, date: c.date, title: c.author, text: c.message, label: c.channel })),
          ...(widget.selector === 'activity' ? data.issues.map(i => ({ id: i.id, date: i.date, title: i.title, text: i.detail, label: i.status })) : []),
        ];
  if (!rows.length) return <Empty/>;
  return <div className="timeline">{rows.sort((a, b) => b.date.localeCompare(a.date)).map(r => <div className="timeline-item" key={r.id}><span className="timeline-dot"/><div className="row between"><strong>{r.title}</strong><time>{r.date.slice(5)}</time></div><p>{r.text}</p><span className="source">{r.label} · {r.id}</span></div>)}</div>;
}
function TaskList({ data, completed, onToggleTask }: WidgetProps) {
  if (!data.tasks.length) return <Empty message="No open tasks in this scope."/>;
  return <div className="task-list">{[...data.tasks].sort((a, b) => a.due_date.localeCompare(b.due_date)).map(t => <div className={`task ${completed.has(t.id) ? 'done' : ''}`} key={t.id}><button className="task-check" aria-label={`${completed.has(t.id) ? 'Reopen' : 'Complete'} ${t.title} locally`} aria-pressed={completed.has(t.id)} onClick={() => onToggleTask(t.id)}>{completed.has(t.id) ? <CheckCircle2 size={20}/> : <Circle size={20}/>}</button><div><strong>{t.title}</strong><p>{t.owner} <span>·</span> {t.due_date}</p></div><span className={`badge ${!completed.has(t.id) && t.due_date < DEMO_DATE ? 'pink' : ''}`}>{completed.has(t.id) ? 'Done locally' : t.due_date < DEMO_DATE ? 'Overdue' : t.status}</span></div>)}<p className="footnote">Task check-offs are local to this browser session.</p></div>;
}
function ProjectProgress({ data, onIntent }: WidgetProps) {
  if (!data.projects.length) return <Empty message="No projects are behind schedule in this scope."/>;
  return <div className="projects-list">{data.projects.map(p => <div className="project" key={p.id}><div className="row between"><div><h3>{p.name}</h3><p>{p.owner} · Due {p.due_date}</p></div><span className={`badge ${p.progress < p.expected ? 'pink' : 'green'}`}>{p.status}</span></div><div className="progress-track"><div style={{ width: `${p.progress}%` }}/><span style={{ left: `${p.expected}%` }} title={`Expected ${p.expected}%`}/></div><div className="row between"><span className="muted">{p.progress}% complete <span className="expected">/ {p.expected}% expected</span></span><button className="text-button" onClick={() => onIntent(`Review projects for ${p.client_id}`)}>Focus client <ArrowUpRight size={13}/></button></div></div>)}</div>;
}
function IssuePanel({ data }: WidgetProps) {
  if (!data.issues.length) return <Empty message="No issues match the current filters."/>;
  return <div className="issue-list">{data.issues.map(i => <details key={i.id}><summary><TriangleAlert size={16} className={i.severity === 'High' ? 'pink-text' : 'muted'}/><div><strong>{i.title}</strong><p>{i.owner} · {i.status}</p></div><span className="badge">{i.severity}</span><ChevronDown size={14}/></summary><p>{i.detail}</p><span className="source">{i.id} · {i.date}</span></details>)}</div>;
}
function DataTable({ data, plan, widget }: WidgetProps) {
  const rows = tableRows(data, plan, widget.selector);
  const [ascending, setAscending] = useState(true);
  const [key, setKey] = useState('');
  if (!rows.length) return <Empty/>;
  const cols = Object.keys(rows[0]);
  const sorted = key ? [...rows].sort((a, b) => String(a[key]).localeCompare(String(b[key]), undefined, { numeric: true }) * (ascending ? 1 : -1)) : rows;
  function download() { const csv = [cols, ...sorted.map(r => cols.map(c => String(r[c] ?? '')))].map(row => row.map(v => `"${(/^[=+@\-]/.test(v) ? "'" : '') + v.replaceAll('"', '""')}"`).join(',')).join('\r\n'); const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); const a = document.createElement('a'); a.href = url; a.download = `kairos-${widget.selector}.csv`; a.click(); URL.revokeObjectURL(url); }
  return <><div className="table-toolbar"><span className="muted">{rows.length} records · click a heading to sort</span><button className="text-button" onClick={download}><Download size={14}/> Export CSV</button></div><div className="table-scroll"><table><thead><tr>{cols.map(c => <th key={c} aria-sort={key === c ? ascending ? 'ascending' : 'descending' : 'none'}><button onClick={() => { setKey(c); setAscending(key === c ? !ascending : true); }}>{c}{key === c ? ascending ? ' ↑' : ' ↓' : ''}</button></th>)}</tr></thead><tbody>{sorted.map((r, i) => <tr key={i}>{cols.map(c => <td key={c}>{String(r[c] ?? '—')}</td>)}</tr>)}</tbody></table></div></>;
}
function InsightPanel({ data, plan }: WidgetProps) {
  const rows = insights(data, plan);
  if (!rows.length) return <Empty message="There is not enough evidence in this scope to suggest an insight."/>;
  return <div className="insights">{rows.map((r, i) => <div key={i}><span className={`badge ${r.kind === 'Hypothesis' ? 'pink' : r.kind === 'Observation' ? 'blue' : ''}`}>{r.kind}</span><p>{r.text}</p><span className="source">{r.source}</span></div>)}</div>;
}
export const registry: Record<WidgetPlan['type'], ComponentType<WidgetProps>> = { ClientProfile, MeetingBrief, UsageChart, MetricCards, ActivityTimeline, TaskList, ProjectProgress, IssuePanel, DataTable, InsightPanel };
