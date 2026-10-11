/** Functional, authenticated SORYU workspace views.  Presentation ONLY.
 * All rows originate from the server's employee-scoped v2 response. UI controls
 * recompose through the authenticated planner; no direct Supabase data reads.
 */
import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUpRight, CalendarDays, ChevronDown, Clock3, ExternalLink, GitBranch, Layers3, Table2 } from 'lucide-react';
import { ResponsiveContainer, CartesianGrid, Bar, BarChart, Cell, Line, LineChart, Pie, PieChart, Tooltip, XAxis, YAxis } from 'recharts';
import type { EnterpriseResponse } from '../../ai/enterprise';
import { apiRequest } from '../../lib/api';
import './functional-workspace.css';

type R = Record<string, unknown>;
type View = 'calendar' | 'workload' | 'usage' | 'portfolio' | 'incidents' | 'dependencies' | null;
const str = (v: unknown) => v === undefined || v === null ? '' : String(v);
const num = (v: unknown) => Number.isFinite(Number(v)) ? Number(v) : 0;
const arr = (v: unknown): R[] => Array.isArray(v) ? v.filter((row): row is R => Boolean(row && typeof row === 'object' && !Array.isArray(row))) : [];
const data = (r: EnterpriseResponse, key: string) => arr(r.datasets[key]);
const isoAdd = (day: string, days: number) => {
  const date = new Date(`${day}T12:00:00Z`);
  if (Number.isNaN(date.valueOf())) return day;
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0,10);
};
const formatDate = (day: string) => new Intl.DateTimeFormat('en-GB', {weekday:'short', day:'numeric', month:'short', timeZone:'UTC'}).format(new Date(`${day}T12:00:00Z`));
const zoneDate = (timestamp: string, timeZone: string) => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return '';
  const parts = new Intl.DateTimeFormat('en-GB', {timeZone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(date);
  const key = (type: string) => parts.find(p => p.type === type)?.value || '';
  return `${key('year')}-${key('month')}-${key('day')}`;
};
const formatTime = (timestamp: string, timeZone: string) => {
  const d = new Date(timestamp);
  return Number.isNaN(d.valueOf()) ? 'Unknown time' : new Intl.DateTimeFormat('en-GB', {timeZone, hour:'2-digit', minute:'2-digit', hour12:true}).format(d);
};
export function selectedFunctionalView(result: EnterpriseResponse): View {
  const intent = result.intent.name;
  if (intent === 'team_workload_planning' && data(result,'schedule_summary').length) return 'calendar';
  if (intent === 'team_workload_planning' && data(result,'workload_chart').length) return 'workload';
  if (intent === 'product_usage_investigation' && data(result,'usage').length) return 'usage';
  if (intent === 'executive_briefing' && data(result,'portfolio_summary').length) return 'portfolio';
  if (intent === 'support_incident_command' && data(result,'issues').length) return 'incidents';
  if (intent === 'project_delivery_review' && data(result,'projects').length) return 'dependencies';
  return null;
}

type EvidenceDrawerProps = {result:EnterpriseResponse; evidenceIds?:string[]; title:string; onClose:()=>void};
function EvidenceDrawer({result,evidenceIds=[],title,onClose}:EvidenceDrawerProps) {
  const [response,setResponse] = useState('');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState('');
  const found = [...new Set(evidenceIds)].map(id => result.evidence.find(e=>e.id===id)).filter((e):e is EnterpriseResponse['evidence'][number]=>!!e);
  async function read(id:string) {
    setBusy(id);setResponse('');setError('');
    try {
      const item = found.find(e=>e.id===id);
      if (!item) return;
      if (item.navigation.kind==='knowledge_document' && item.navigation.document_id) {
        const r = await apiRequest<{body:string}>(`/api/intelligence/knowledge/documents/${encodeURIComponent(item.navigation.document_id)}`);
        setResponse(r.body);
      } else {
        const r = await apiRequest<{value:unknown}>(`/api/intelligence/evidence/${encodeURIComponent(id)}`);
        setResponse(JSON.stringify(r.value,null,2));
      }
    } catch(e) {setError(e instanceof Error?e.message:'Unable to load evidence.');}
    finally {setBusy('');}
  }
  return <section className="fw-drawer" aria-label="Record details">
    <div className="fw-row"><strong>{title}</strong><button type="button" onClick={onClose}>Close</button></div>
    <p className="fw-muted">Only evidence already referenced by this authenticated response can be opened.</p>
    <div className="fw-evidence-buttons">{found.length ? found.map(e=><button key={e.id} onClick={()=>void read(e.id)} disabled={busy===e.id}><ExternalLink size={12}/>{e.title}{busy===e.id?' · Loading':''}</button>) : <span>No evidence links in this result.</span>}</div>
    {error && <p role="alert">{error}</p>}{response && <pre>{response}</pre>}
  </section>;
}

function Surface({title,caption,children}:{title:string;caption?:string;children:React.ReactNode}) {
  return <section className="fw-surface"><div className="fw-heading"><div><h3>{title}</h3>{caption&&<p>{caption}</p>}</div></div>{children}</section>;
}

type CalendarEvent = {id:string; title:string; starts_at:string; ends_at:string; employee_id?:string; project_name?:string; source:string; evidence_ids:string[]; block_type?:string};
function WeeklyCalendar({result,onIntent}:{result:EnterpriseResponse;onIntent:(prompt:string)=>void}) {
  const summary = data(result,'schedule_summary')[0];
  const weekStart = str(summary?.date_from || result.intent.date_from);
  const weekEnd = str(summary?.date_to || (weekStart && isoAdd(weekStart,6)));
  const options = data(result,'employee_options');
  const selectedIds = Array.isArray(summary?.employee_ids) ? summary.employee_ids.map(str) : [];
  const employeeName = str((Array.isArray(summary?.employee_names) ? summary.employee_names[0] : '') || options.find(e=>selectedIds.includes(str(e.id)))?.employee_name || 'Selected employee');
  const groupTarget = str(summary?.focus_label || employeeName);
  const targetName = selectedIds.length > 1 ? groupTarget : employeeName;
  const [chosen,setChosen] = useState('');
  const [zone,setZone] = useState('Asia/Kolkata');
  const [overlay,setOverlay] = useState(false);
  const [focused,setFocused] = useState<CalendarEvent|null>(null);
  const [sourceOpen,setSourceOpen] = useState(false);
  const rawBlocks = data(result,'schedule_events').map(row => ({
    id:str(row.id), title:str(row.block_type || 'Reserved schedule block'), starts_at:str(row.starts_at), ends_at:str(row.ends_at),
    employee_id:str(row.employee_id), project_name:str(row.project_name), block_type:str(row.block_type),
    source:'Recorded block', evidence_ids:Array.isArray(row.evidence_ids)?row.evidence_ids.map(str):[],
  }));
  const rawMeetings = data(result,'schedule_meetings').map(row => ({
    id:str(row.id), title:str(row.title || 'Recorded meeting'), starts_at:str(row.starts_at), ends_at:str(row.ends_at),
    source:'Meeting record', evidence_ids:Array.isArray(row.evidence_ids)?row.evidence_ids.map(str):[],
  }));
  // Pass 10: new meetings intentionally create both a meeting row and a booking
  // block. Keep the independent meeting-record count, but avoid drawing two
  // overlapping event tiles for the same recorded booking.
  const visibleMeetings=rawMeetings.filter(m=>!rawBlocks.some(b=>b.block_type==='Meeting' && b.starts_at===m.starts_at && b.ends_at===m.ends_at));
  const events:CalendarEvent[] = [...rawBlocks,...visibleMeetings].filter(ev=>ev.starts_at&&ev.ends_at && Number.isFinite(new Date(ev.starts_at).getTime()));
  const days = Array.from({length:weekStart && weekEnd ? Math.min(7,Math.floor((Date.parse(weekEnd+'T12:00:00Z')-Date.parse(weekStart+'T12:00:00Z'))/86400000)+1) : 0},(_,i)=>isoAdd(weekStart,i));
  const earliest = Math.max(0,Math.min(8,...events.map(e=>new Date(e.starts_at).toLocaleString('en-US',{hour:'numeric',hour12:false,timeZone:zone})).map(Number).filter(Number.isFinite)));
  const latest = Math.min(24,Math.max(19,...events.map(e=>new Date(e.ends_at).toLocaleString('en-US',{hour:'numeric',hour12:false,timeZone:zone})).map(Number).filter(Number.isFinite).map(h=>h+1)));
  const timeStart = Number.isFinite(earliest)?earliest:8;
  const timeEnd = Number.isFinite(latest)&&latest>timeStart?latest:20;
  const times = Array.from({length:timeEnd-timeStart+1},(_,i)=>timeStart+i);
  const sourceIds = (ev:CalendarEvent) => ev.evidence_ids;
  const people = options.length ? options : selectedIds.map((id,i)=>({id,employee_name:i===0?employeeName:id}));
  function requestWeek(nextStart:string, name=targetName) {
    onIntent(`Show ${name}'s schedule from ${nextStart} to ${isoAdd(nextStart,6)}`);
  }
  function coordinate(t:string) {
    const parts = new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(t));
    const h = Number(parts.find(p=>p.type==='hour')?.value||0);
    const m = Number(parts.find(p=>p.type==='minute')?.value||0);
    return h+m/60;
  }
  const chart = data(result,'workload_chart');
  const activeRow = chart.find(r=>selectedIds.includes(str(r.employee_id)));
  return <Surface title="Employee weekly timetable" caption="Recorded blocks and meetings only · Changes re-query authorized SORYU records">
    <div className="fw-calendar-controls">
      <div className="fw-week-nav"><button aria-label="Previous week" onClick={()=>requestWeek(isoAdd(weekStart,-7))}><ArrowLeft size={15}/></button><strong>{weekStart?formatDate(weekStart):'Week'} – {weekEnd?formatDate(weekEnd):''}</strong><button aria-label="Next week" onClick={()=>requestWeek(isoAdd(weekStart,7))}><ArrowRight size={15}/></button></div>
      <label>Employee<select aria-label="Select employee" value={chosen || (selectedIds.length===1?selectedIds[0]:'')} onChange={e=>{const next=e.target.value;setChosen(next);const person=people.find(r=>str(r.id)===next);if(person)requestWeek(weekStart,str(person.employee_name));else if(selectedIds.length>1)requestWeek(weekStart,groupTarget);}}><option value="">{selectedIds.length>1 ? `All — ${groupTarget}` : "Choose employee"}</option>{people.map(p=><option value={str(p.id)} key={str(p.id)}>{str(p.employee_name)}</option>)}</select></label>
      <label>Time zone<select aria-label="Calendar time zone" value={zone} onChange={e=>setZone(e.target.value)}><option value="Asia/Kolkata">IST (India)</option><option value="UTC">UTC</option>{Intl.DateTimeFormat().resolvedOptions().timeZone && !['UTC','Asia/Kolkata'].includes(Intl.DateTimeFormat().resolvedOptions().timeZone)&&<option value={Intl.DateTimeFormat().resolvedOptions().timeZone}>My local zone</option>}</select></label>
      <label className="fw-toggle"><input aria-label="Show workload overlay" type="checkbox" checked={overlay} onChange={e=>setOverlay(e.target.checked)}/> Workload overlay</label>
    </div>
    <div className="fw-kpis"><div><strong>{num(summary?.recorded_block_count)}</strong><span>Recorded blocks</span></div><div><strong>{num(summary?.merged_booked_hours).toFixed(1)}h</strong><span>Reserved intervals</span></div><div><strong>{rawMeetings.length}</strong><span>Meeting records</span></div></div>
    {overlay && <div className="fw-overlay"><strong>Estimated task backlog: {activeRow?num(activeRow.estimated_backlog_hours):'—'}h</strong><span> · {activeRow?num(activeRow.open_tasks):'—'} open tasks. Backlog is unscheduled work and is not placed onto calendar days.</span></div>}
    <div className="fw-calendar-scroll"><div className="fw-calendar-grid" style={{'--fw-hours':times.length-1} as React.CSSProperties}>
      <div className="fw-time-head">{zone==='Asia/Kolkata'?'IST':zone==='UTC'?'UTC':'Local'}</div>
      {days.map(d=><div key={d} className="fw-day-head"><span>{formatDate(d)}</span><small>{events.filter(e=>zoneDate(e.starts_at,zone)===d).length} recorded</small></div>)}
      <div className="fw-time-labels">{times.map(h=><div key={h}>{`${String(h).padStart(2,'0')}:00`}</div>)}</div>
      {days.map(d=><div key={d} className="fw-day-track" style={{height:`${(timeEnd-timeStart)*54}px`}}>
        {times.slice(0,-1).map(h=><div className="fw-hour-row" key={h}/>)}
        {events.filter(e=>zoneDate(e.starts_at,zone)===d).map(e=>{
          const start=coordinate(e.starts_at),end=coordinate(e.ends_at);
          const top=Math.max(0,(start-timeStart)*54), height=Math.max(28,Math.min((timeEnd-timeStart)*54-top,(end-start)*54));
          return <button key={e.id} title={`${e.title} · ${formatTime(e.starts_at,zone)}`} className={`fw-event ${e.source==='Meeting record'?'fw-meeting':''}`} style={{top:`${top}px`,height:`${height}px`}} onClick={()=>{setFocused(e);setSourceOpen(false);}}><strong>{e.title}</strong><small>{formatTime(e.starts_at,zone)}</small></button>;
        })}
      </div>)}
    </div></div>
    <p className="fw-footnote">Blank space means no booking was returned, not that an employee is available. Overlapping blocks are not double-counted in reserved interval totals. Calendar times are displayed in {zone}.</p>
    {focused && <div className="fw-event-inspector"><div className="fw-row"><h4>{focused.title}</h4><button onClick={()=>setFocused(null)}>Close</button></div><p>{formatDate(zoneDate(focused.starts_at,zone))} · {formatTime(focused.starts_at,zone)}–{formatTime(focused.ends_at,zone)} · {focused.source}</p>{focused.project_name&&<p>Project: {focused.project_name}</p>}<button onClick={()=>setSourceOpen(!sourceOpen)}><ExternalLink size={13}/> {sourceOpen?'Hide evidence':'Inspect source record'}</button>{sourceOpen&&<EvidenceDrawer title={focused.title} result={result} evidenceIds={sourceIds(focused)} onClose={()=>setSourceOpen(false)}/>}</div>}
  </Surface>;
}

function WorkloadChart({result}:{result:EnterpriseResponse}) {
  const rows=data(result,'workload_chart').map(r=>({id:str(r.id),name:str(r.employee_name),backlog:num(r.estimated_backlog_hours),booked:num(r.scheduled_interval_hours),tasks:num(r.open_tasks),evidence_ids:Array.isArray(r.evidence_ids)?r.evidence_ids.map(str):[]}));
  const [sort,setSort]=useState<'backlog'|'name'>('backlog');
  const [detail,setDetail]=useState<typeof rows[number]|null>(null);
  const sorted=[...rows].sort((a,b)=>sort==='backlog'?b.backlog-a.backlog:a.name.localeCompare(b.name));
  return <Surface title="Employee workload comparison" caption="Estimated remaining task hours versus recorded calendar blocks">
    <div className="fw-toolbar"><label>Order<select value={sort} onChange={e=>setSort(e.target.value as typeof sort)}><option value="backlog">Highest backlog first</option><option value="name">Employee A–Z</option></select></label></div>
    <div className="fw-chart" role="img" aria-label="Estimated backlog and booked intervals by employee"><ResponsiveContainer width="100%" height={Math.max(260,sorted.length*34)}><BarChart data={sorted} layout="vertical" margin={{top:8,right:35,bottom:8,left:15}}><CartesianGrid stroke="#31404f" strokeDasharray="3 5" horizontal={false}/><XAxis type="number" tick={{fill:'#b7c7d8'}}/><YAxis dataKey="name" type="category" width={120} tick={{fill:'#d9e5f0',fontSize:11}}/><Tooltip contentStyle={{background:'#1b2632',border:'1px solid #566378',color:'#fff'}}/><Bar dataKey="backlog" name="Estimated backlog hours" fill="#e57691" radius={[0,3,3,0]}/><Bar dataKey="booked" name="Recorded calendar hours" fill="#64c9d6" radius={[0,3,3,0]}/></BarChart></ResponsiveContainer></div>
    <div className="fw-table-scroll"><table><thead><tr><th>Employee</th><th>Open tasks</th><th>Est. backlog (h)</th><th>Booked intervals (h)</th><th>Evidence</th></tr></thead><tbody>{sorted.map(r=><tr key={r.id}><td>{r.name}</td><td>{r.tasks}</td><td>{r.backlog}</td><td>{r.booked}</td><td><button onClick={()=>setDetail(r)}>Inspect</button></td></tr>)}</tbody></table></div>
    <p className="fw-footnote">Task estimates may span multiple weeks. Backlog is not a weekly commitment; recorded calendar intervals are not a complete statement of availability.</p>
    {detail&&<EvidenceDrawer result={result} evidenceIds={detail.evidence_ids} title={detail.name} onClose={()=>setDetail(null)}/>}</Surface>;
}

function UsageAnalytics({result}:{result:EnterpriseResponse}) {
  const items=data(result,'usage');
  const metrics=data(result,'usage_metrics');
  const combos=[...new Set(items.map(r=>`${str(r.client_id)}::${str(r.product_id)}`))];
  const [combo,setCombo]=useState(combos[0]||'');
  const [days,setDays]=useState('all');
  const [table,setTable]=useState(false);
  const filtered=items.filter(r=>`${str(r.client_id)}::${str(r.product_id)}`===combo);
  const perDay = new Map<string,number[]>();
  filtered.forEach(r=>{const day=str(r.date).slice(0,10);perDay.set(day,[...(perDay.get(day)||[]),num(r.active_users)]);});
  const series=[...perDay.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([date,values])=>({date,active_users:Math.round(values.reduce((a,b)=>a+b,0)/values.length*100)/100}));
  const latest=series[series.length-1]?.date;
  const from=latest&&days!=='all'?isoAdd(latest,-Number(days)+1):'';
  const visible=from?series.filter(s=>s.date>=from):series;
  const metric=metrics.find(m=>`${str(m.client_id)}::${str(m.product_id)}`===combo);
  return <Surface title="Product adoption and usage" caption="Measured daily active users · absent days are missing data, not zero">
    <div className="fw-toolbar"><label>Client / product<select value={combo} onChange={e=>setCombo(e.target.value)}>{combos.map(c=><option key={c} value={c}>{c.replace('::',' / ')}</option>)}</select></label><label>Visible window<select value={days} onChange={e=>setDays(e.target.value)}><option value="all">All fetched dates</option><option value="7">Latest 7 dates</option><option value="14">Latest 14 dates</option><option value="30">Latest 30 dates</option></select></label><button onClick={()=>setTable(!table)}><Table2 size={14}/>{table?'Show chart':'Show table'}</button></div>
    {metric&&<div className="fw-kpis"><div><strong>{num(metric.average_daily_active_users).toFixed(1)}</strong><span>Average DAU</span></div><div><strong>{metric.change_percent==null?'N/A':`${num(metric.change_percent)}%`}</strong><span>Preceding-period change</span></div><div><strong>{num(metric.measured_days)}</strong><span>Measured days</span></div></div>}
    {table?<div className="fw-table-scroll"><table><thead><tr><th>Date</th><th>Average active users</th></tr></thead><tbody>{visible.map(row=><tr key={row.date}><td>{row.date}</td><td>{row.active_users}</td></tr>)}</tbody></table></div>:<div className="fw-chart" role="img" aria-label="Daily active users"><ResponsiveContainer width="100%" height={300}><LineChart data={visible} margin={{top:14,right:20,bottom:8,left:3}}><CartesianGrid stroke="#31404f" strokeDasharray="3 5"/><XAxis dataKey="date" tick={{fill:'#b8c8d6',fontSize:10}} minTickGap={20}/><YAxis tick={{fill:'#b8c8d6'}} domain={['auto','auto']}/><Tooltip contentStyle={{background:'#1b2632',border:'1px solid #566378',color:'#fff'}}/><Line type="monotone" dataKey="active_users" name="Daily active users" stroke="#73d9ed" strokeWidth={2.5} connectNulls={false}/></LineChart></ResponsiveContainer></div>}
    <p className="fw-footnote">Date filters apply only to records the authorized backend returned. Trends do not establish incident causation.</p>
  </Surface>;
}

function Portfolio({result}:{result:EnterpriseResponse}) {
  const p=data(result,'portfolio_summary')[0];
  const totals=[{name:'Delayed',count:num(p?.delayed_projects),color:'#df7086'},{name:'At risk',count:num(p?.at_risk_projects),color:'#edbd82'},{name:'On track',count:num(p?.on_track_projects),color:'#72cab6'}];
  const projects=data(result,'projects');
  const [status,setStatus]=useState('Delayed');
  const [selected,setSelected]=useState<R|null>(null);
  const filtered=projects.filter(r=>status==='All'||str(r.status).toLowerCase()===status.toLowerCase()).sort((a,b)=>num(a.progress)-num(b.progress));
  return <Surface title="Executive company health" caption="Portfolio KPIs and prioritized project drill-downs">
    <div className="fw-kpis"><div><strong>{num(p?.delayed_projects)}</strong><span>Delayed projects</span></div><div><strong>{num(p?.at_risk_projects)}</strong><span>At-risk projects</span></div><div><strong>{num(p?.on_track_projects)}</strong><span>On-track projects</span></div><div><strong>{num(p?.contracts_renewal_due)}</strong><span>Renewal due</span></div></div>
    <div className="fw-chart fw-portfolio" role="img" aria-label="Project health status distribution"><ResponsiveContainer width="100%" height={230}><PieChart><Tooltip contentStyle={{background:'#1b2632',border:'1px solid #566378',color:'#fff'}}/><Pie data={totals} dataKey="count" nameKey="name" innerRadius={65} outerRadius={95} label={(props:{name?:string;value?:number})=>`${props.name}: ${props.value}`}>{totals.map(t=><Cell key={t.name} fill={t.color}/>)}</Pie></PieChart></ResponsiveContainer></div>
    <div className="fw-toolbar"><label>Project status<select value={status} onChange={e=>setStatus(e.target.value)}><option>Delayed</option><option>At risk</option><option>On track</option><option>All</option></select></label></div>
    <div className="fw-table-scroll"><table><thead><tr><th>Project</th><th>Status</th><th>Actual</th><th>Expected</th><th>Gap</th><th>Details</th></tr></thead><tbody>{filtered.map(row=><tr key={str(row.id)}><td>{str(row.name)}</td><td>{str(row.status)}</td><td>{num(row.progress)}%</td><td>{num(row.expected)}%</td><td>{num(row.progress)-num(row.expected)} pp</td><td><button onClick={()=>setSelected(row)}>Details</button></td></tr>)}</tbody></table></div>
    {selected&&<EvidenceDrawer title={str(selected.name)} result={result} evidenceIds={result.evidence.filter(e=>e.id.startsWith(`db:projects:${str(selected.id)}:`)).map(e=>e.id)} onClose={()=>setSelected(null)}/>}
    <p className="fw-footnote">Recorded project status and progress are not causal explanations. Renewal-due status does not establish lost revenue.</p>
  </Surface>;
}

function Incidents({result}:{result:EnterpriseResponse}) {
  const incidents=data(result,'issues').sort((a,b)=>{
    const weight=(r:R)=>str(r.severity).toLowerCase()==='critical'?0:str(r.severity).toLowerCase()==='high'?1:2;
    return weight(a)-weight(b)||str(a.id).localeCompare(str(b.id));
  });
  const [severity,setSeverity]=useState('All');
  const owners=new Map(data(result,'employee_directory').map(e=>[str(e.id),str(e.name)]));
  const [detail,setDetail]=useState<R|null>(null);
  const shown=incidents.filter(r=>severity==='All'||str(r.severity).toLowerCase()===severity.toLowerCase());
  return <Surface title="Priority support incident command" caption="Unresolved, high-severity incidents · severity first, then recorded status">
    <div className="fw-kpis"><div><strong>{incidents.filter(i=>str(i.severity).toLowerCase()==='critical').length}</strong><span>Critical incidents</span></div><div><strong>{incidents.filter(i=>str(i.severity).toLowerCase()==='high').length}</strong><span>High incidents</span></div><div><strong>{incidents.length}</strong><span>Visible unresolved records</span></div></div>
    <div className="fw-toolbar"><label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value)}><option>All</option><option>Critical</option><option>High</option></select></label></div>
    <div className="fw-table-scroll"><table><thead><tr><th>Priority</th><th>Incident</th><th>Status</th><th>Recorded owner</th><th>Recorded SLA duration</th><th>Evidence</th></tr></thead><tbody>{shown.map(row=><tr key={str(row.id)}><td><span className={`fw-severity ${str(row.severity).toLowerCase()}`}>{str(row.severity)}</span></td><td>{str(row.title)}</td><td>{str(row.status)}</td><td>{owners.get(str(row.owner_employee_id)) || str(row.owner_employee_id) || 'Not recorded'}</td><td>{row.sla_hours==null?'Unknown':`${num(row.sla_hours)} h`}</td><td><button onClick={()=>setDetail(row)}>Inspect</button></td></tr>)}</tbody></table></div>
    <p className="fw-footnote">An SLA duration is not an SLA-breach timestamp. Click Inspect for the source incident record.</p>
    {detail&&<EvidenceDrawer result={result} title={str(detail.title)} evidenceIds={result.evidence.filter(e=>e.id.startsWith(`db:issues:${str(detail.id)}:`)).map(e=>e.id)} onClose={()=>setDetail(null)}/>}
  </Surface>;
}

function Dependencies({result}:{result:EnterpriseResponse}) {
  const nodes=data(result,'task_nodes');
  const edges=data(result,'task_dependencies');
  const byId=new Map(nodes.map(n=>[str(n.id),n]));
  const [selected,setSelected]=useState<R|null>(null);
  return <Surface title="Task dependency and blocker graph" caption="Recorded directed links only: dependent task → blocking task">
    {edges.length ? <div className="fw-graph">{edges.map(edge=>{
      const child=byId.get(str(edge.dependent_task_id)),blocker=byId.get(str(edge.blocker_task_id));
      if(!child||!blocker)return null;
      return <div className="fw-dependency" key={str(edge.id)}><button onClick={()=>setSelected(child)}><strong>{str(child.title)}</strong><small>{str(child.status)} · {str(child.owner_name)||'Owner unknown'}</small></button><div className="fw-link"><GitBranch size={17}/><span>blocked by</span><ArrowRight size={17}/></div><button onClick={()=>setSelected(blocker)}><strong>{str(blocker.title)}</strong><small>{str(blocker.status)} · {str(blocker.owner_name)||'Owner unknown'}</small></button></div>;
    })}</div> : <div className="fw-no-links"><Layers3 size={20}/><p>No explicit blocker-to-task relationships were returned for these visible projects. A delayed status alone does not establish a dependency.</p></div>}
    <p className="fw-footnote">A blocker relationship records a dependency; it does not independently establish why a whole project is delayed.</p>
    {selected&&<EvidenceDrawer result={result} title={str(selected.title)} evidenceIds={Array.isArray(selected.evidence_ids)?selected.evidence_ids.map(str):[]} onClose={()=>setSelected(null)}/>}
  </Surface>;
}

export function FunctionalWorkspace({result,onIntent}:{result:EnterpriseResponse;onIntent:(prompt:string)=>void}) {
  const view=selectedFunctionalView(result);
  if (!view) return null;
  return <div className="fw-root" data-functional-view={view}>
    <div className="fw-context"><span><CalendarDays size={14}/> Adaptive workspace</span><span>{view === 'calendar'?'WEEKLY TIMETABLE':view === 'workload'?'WORKLOAD CHART':view === 'usage'?'USAGE TRENDS':view === 'portfolio'?'EXECUTIVE ANALYTICS':view === 'incidents'?'INCIDENT COMMAND':'PROJECT DEPENDENCIES'}</span></div>
    {view==='calendar'&&<WeeklyCalendar key={str(data(result,'schedule_summary')[0]?.id)} result={result} onIntent={onIntent}/>}
    {view==='workload'&&<WorkloadChart result={result}/>}
    {view==='usage'&&<UsageAnalytics result={result}/>}
    {view==='portfolio'&&<Portfolio result={result}/>}
    {view==='incidents'&&<Incidents result={result}/>}
    {view==='dependencies'&&<><Dependencies result={result}/><PortfolioProjects result={result}/></>}
  </div>;
}

function PortfolioProjects({result}:{result:EnterpriseResponse}) {
  const projects=data(result,'projects');
  if (!projects.length) return null;
  return <Surface title="Delivery gap comparison" caption="Actual versus expected progress — percent of project completion"><div className="fw-chart" role="img" aria-label="Project delivery completion against expected"><ResponsiveContainer width="100%" height={Math.max(220,projects.length*48)}><BarChart data={projects.map(p=>({name:str(p.name),actual:num(p.progress),expected:num(p.expected)}))} layout="vertical" margin={{top:5,right:25,bottom:5,left:10}}><CartesianGrid stroke="#31404f" strokeDasharray="3 5" horizontal={false}/><XAxis type="number" domain={[0,100]} tick={{fill:'#becbd8'}}/><YAxis type="category" dataKey="name" width={185} tick={{fill:'#d5e5f0',fontSize:11}}/><Tooltip contentStyle={{background:'#1b2632',border:'1px solid #566378',color:'#fff'}}/><Bar dataKey="actual" name="Recorded progress (%)" fill="#e57691" radius={[0,3,3,0]}/><Bar dataKey="expected" name="Expected progress (%)" fill="#69c7d3" radius={[0,3,3,0]}/></BarChart></ResponsiveContainer></div></Surface>;
}
