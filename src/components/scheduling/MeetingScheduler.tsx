/** SORYU meeting creation. No synthetic employee lists or client data. */
import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, BrainCircuit, CalendarPlus, CheckCircle2, Clock, Loader2, Search, ShieldCheck, Users, X } from 'lucide-react';
import { apiRequest } from '../../lib/api';
import './meeting-scheduler.css';
import { ReflexComparison } from './ReflexComparison';
import type { ReflexResult } from './ReflexComparison';

type Employee = {id:string; full_name:string; department_id:string; department:string; job_title:string};
type Client = {id:string; name:string};
type Project = {id:string; name:string; client_id:string};
type Options = {current_employee_id:string;employees:Employee[];clients:Client[];projects:Project[];time_zone:string};
type Proposal = {title:string;client_id:string;project_id:string|null;purpose:string;starts_at:string;ends_at:string;participant_employee_ids:string[];idempotency_key:string};
type Booking = {id:string;title:string;starts_at:string;ends_at:string;organizer_employee_id:string;participant_employee_ids:string[];schedule_block_ids?:string[];replayed:boolean};
type Clash = {employee_id:string;employee_name:string;source_type:string;source_id:string;title:string;starts_at:string;ends_at:string};
type Preview = {can_create:boolean;client:Client;project:Project|null;participants:Employee[];organizer_employee_id:string;starts_at:string;ends_at:string;duration_minutes:number;conflicts:Clash[];truncated:boolean;notice:string};

const newRequestId = () => crypto.randomUUID();
export const istDay = (iso:string):string => {
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(iso));
  const value=(key:string)=>parts.find(p=>p.type===key)?.value||'';
  return `${value('year')}-${value('month')}-${value('day')}`;
};
const timeText = (iso:string) => new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(iso));
function defaultLocalIST():string {
  const d = new Date(Date.now()+ (330+90)*60_000);
  d.setUTCMinutes(Math.ceil(d.getUTCMinutes()/30)*30,0,0);
  return d.toISOString().slice(0,16);
}
export function localISTtoUTC(value:string):string {
  const instant = new Date(`${value}:00+05:30`);
  if (Number.isNaN(instant.valueOf())) throw new Error('Choose a valid meeting date and time.');
  return instant.toISOString();
}
export function makeProposal(value:{title:string;clientId:string;projectId:string;purpose:string;startLocal:string;duration:number;attendees:string[];requestId:string}):Proposal {
  const start = localISTtoUTC(value.startLocal);
  return {title:value.title.trim(),client_id:value.clientId,project_id:value.projectId||null,purpose:value.purpose.trim(),starts_at:start,
    ends_at:new Date(new Date(start).valueOf()+value.duration*60_000).toISOString(),
    participant_employee_ids:[...new Set(value.attendees)].sort(),idempotency_key:value.requestId};
}

export function MeetingScheduler({onClose,onCreated}:{onClose:()=>void;onCreated:(dateIST:string)=>void}) {
  const [options,setOptions]=useState<Options|null>(null);
  const [step,setStep]=useState<'edit'|'review'|'created'>('edit');
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [title,setTitle]=useState('');
  const [clientId,setClientId]=useState('');
  const [projectId,setProjectId]=useState('');
  const [purpose,setPurpose]=useState('');
  const [startLocal,setStartLocal]=useState(defaultLocalIST);
  const [duration,setDuration]=useState(60);
  const [attendees,setAttendees]=useState<string[]>([]);
  const [search,setSearch]=useState('');
  const [requestId,setRequestId]=useState(newRequestId);
  const [proposal,setProposal]=useState<Proposal|null>(null);
  const [preview,setPreview]=useState<Preview|null>(null);
  const [reflex,setReflex]=useState<{key:string;data:ReflexResult}|null>(null);
  const [reflexBusy,setReflexBusy]=useState(false);
  const [reflexError,setReflexError]=useState('');
  const [created,setCreated]=useState<Booking|null>(null);
  useEffect(()=>{
    let active=true;
    setLoading(true);
    apiRequest<Options>('/api/intelligence/scheduling/options')
      .then(data=>{if(active){setOptions(data);setClientId(prev=>prev||data.clients[0]?.id||'');}})
      .catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load company records.');})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[]);
  const filtered=useMemo(()=>options?.employees.filter(e=>(`${e.full_name} ${e.department} ${e.job_title}`).toLowerCase().includes(search.toLowerCase()))||[],[options,search]);
  const projects=options?.projects.filter(p=>p.client_id===clientId)||[];
  const organizer=options?.employees.find(e=>e.id===options.current_employee_id);
  const chosen=options?.employees.filter(e=>attendees.includes(e.id)&&e.id!==options.current_employee_id)||[];
  function edit(){setStep('edit');setPreview(null);setProposal(null);setError('');}
  function toggle(id:string){setAttendees(p=>p.includes(id)?p.filter(k=>k!==id):[...p,id]);}
  async function handlePreview(event:React.FormEvent){
    event.preventDefault();setError('');
    if(!options||!title.trim()||!clientId)return setError('Complete the meeting title and client first.');
    try {
      const next=makeProposal({title,clientId,projectId,purpose,startLocal,duration,attendees,requestId});
      setLoading(true);
      const res=await apiRequest<Preview>('/api/intelligence/scheduling/preview',{method:'POST',body:JSON.stringify(next)});
      setProposal(next);setPreview(res);setStep('review');
    }catch(e){setError(e instanceof Error?e.message:'Unable to preview the meeting.');}
    finally{setLoading(false);}
  }
  const reflexKey=JSON.stringify([title,clientId,projectId,purpose,startLocal,duration,[...attendees].sort()]);
  async function compareWithReflex(){
    if(!options||reflexBusy||loading)return;
    setReflexError('');setReflex(null);setReflexBusy(true);
    try {
      const next=makeProposal({title,clientId,projectId,purpose,startLocal,duration,attendees,requestId});
      const result=await apiRequest<ReflexResult>('/api/intelligence/scheduling/reflex/compare',
        {method:'POST',body:JSON.stringify(next)});
      setReflex({key:reflexKey,data:result});
    }catch(e){setReflexError(e instanceof Error?e.message:'Comparison unavailable. No meeting changed.');}
    finally{setReflexBusy(false);}
  }
  function useReflexSlot(iso:string){
    // Input is always a server-returned timestamp. Convert to the app's IST form.
    const date=new Date(new Date(iso).getTime()+330*60_000);
    setStartLocal(date.toISOString().slice(0,16));
    setReflex(null);setReflexError('');setPreview(null);setProposal(null);
  }
  async function handleConfirm(){
    if(!proposal||!preview?.can_create||loading)return;
    setError('');setLoading(true);
    try {
      const result=await apiRequest<{status:string;meeting:Booking}>('/api/intelligence/scheduling/confirm',
        {method:'POST',body:JSON.stringify({...proposal,confirmed:true})});
      setCreated(result.meeting);setStep('created');
      setRequestId(newRequestId());
    }catch(e){
      const msg=e instanceof Error?e.message:'Creation failed.';
      setError(msg.includes('409')?'A participant has a booking at this time. Nothing was saved. Return to editing and choose another time.':msg);
    }finally{setLoading(false);}
  }
  function onClientChange(next:string){setClientId(next);setProjectId('');}
  const buttonDisabled=loading;
  return <div className="ks-overlay" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="ks-dialog" role="dialog" aria-modal="true" aria-label="Schedule a SORYU meeting">
      <header className="ks-header"><span className="ks-emblem"><CalendarPlus size={22}/></span><div><small>SORYU SYSTEMS · MEETING SCHEDULER</small><h2>Create a meeting</h2><p>Plan a shared booking. Existing calendars are never moved automatically.</p></div><button type="button" className="ks-icon" aria-label="Close meeting scheduler" onClick={onClose}><X size={20}/></button></header>
      <div className="ks-progress"><span className={step==='edit'?'ks-active':''}>1 · Details</span><span className={step==='review'?'ks-active':''}>2 · Review</span><span className={step==='created'?'ks-active':''}>3 · Created</span></div>
      {error&&<div className="ks-error" role="alert">{error}</div>}
      {step==='edit'&&<form className="ks-content" onSubmit={e=>void handlePreview(e)}>
        <div className="ks-field"><label htmlFor="ks-title">Meeting title</label><input id="ks-title" required minLength={3} maxLength={160} value={title} onChange={e=>setTitle(e.target.value)} placeholder="OrbitPay delivery alignment"/></div>
        <div className="ks-grid"><div className="ks-field"><label htmlFor="ks-client">Client</label><select id="ks-client" required value={clientId} onChange={e=>onClientChange(e.target.value)}>{!options?.clients.length&&<option value="">Loading clients…</option>}{options?.clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div className="ks-field"><label htmlFor="ks-project">Linked project (optional)</label><select id="ks-project" value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">No project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div></div>
        <div className="ks-grid"><div className="ks-field"><label htmlFor="ks-start">Date & start time (IST)</label><input id="ks-start" type="datetime-local" required value={startLocal} onChange={e=>setStartLocal(e.target.value)}/></div>
        <div className="ks-field"><label htmlFor="ks-duration">Duration</label><select id="ks-duration" value={duration} onChange={e=>setDuration(Number(e.target.value))}>{[15,30,45,60,90,120,180,240].map(n=><option key={n} value={n}>{n>=60?`${n/60} hour${n>60?'s':''}`:`${n} minutes`}</option>)}</select></div></div>
        <div className="ks-field"><label htmlFor="ks-purpose">Purpose / agenda (optional)</label><textarea id="ks-purpose" maxLength={800} rows={2} value={purpose} onChange={e=>setPurpose(e.target.value)} placeholder="Discuss rollout risks, align deliverables, and confirm next steps"/></div>
        <div className="ks-attendees-title"><div><Users size={17}/><strong>Participants</strong><small>The signed-in organizer is always included.</small></div><span>{chosen.length+1} selected</span></div>
        <div className="ks-organizer"><ShieldCheck size={16}/><span>{organizer?.full_name||'Signed-in employee'} — Organizer</span><small>{organizer?.department}</small></div>
        <label className="ks-search"><Search size={16}/><input aria-label="Filter employees" placeholder="Find people by name or department" value={search} onChange={e=>setSearch(e.target.value)}/></label>
        <div className="ks-list">{filtered.filter(e=>e.id!==options?.current_employee_id).map(e=><label key={e.id} className="ks-person"><input type="checkbox" disabled={!attendees.includes(e.id)&&chosen.length>=11} checked={attendees.includes(e.id)} onChange={()=>toggle(e.id)}/><span>{e.full_name}<small>{e.department} · {e.job_title}</small></span></label>)}</div>
        <button type="button" className="kr-trigger" disabled={buttonDisabled||reflexBusy||!options||!title.trim()||!clientId} onClick={()=>void compareWithReflex()}>
          <BrainCircuit size={17}/> {reflexBusy?'Comparing authorized records…':'KAIROS Reflex · Compare 3 options'}
        </button>
        {reflexError&&<p className="ks-error" role="alert">{reflexError}</p>}
        {reflex?.key===reflexKey&&<ReflexComparison data={reflex.data} onChoose={useReflexSlot}/>}
        <div className="ks-footer"><p>Review does not create or reserve a meeting.</p><button type="submit" className="ks-primary" disabled={buttonDisabled||!options}>{loading?<><Loader2 size={16}/> Checking…</>:'Review meeting →'}</button></div>
      </form>}
      {step==='review'&&preview&&proposal&&<div className="ks-content ks-review">
        <div className="ks-review-card"><small>MEETING PROPOSAL</small><h3>{proposal.title}</h3><p><Clock size={16}/>{timeText(preview.starts_at)} · {preview.duration_minutes} minutes · Asia/Kolkata</p><p><Users size={16}/>{preview.participants.map(e=>e.full_name).join(', ')}</p><p><CalendarPlus size={16}/>{preview.client.name}{preview.project?` · ${preview.project.name}`:''}</p>{proposal.purpose&&<p>{proposal.purpose}</p>}</div>
        <div className={preview.can_create?'ks-info':'ks-warning'}><strong>{preview.can_create?'No recorded overlap found':'Recorded booking overlap'}</strong><p>{preview.notice}</p></div>
        {!!preview.conflicts.length&&<div className="ks-collisions"><h4>Overlapping bookings</h4>{preview.conflicts.map((c,i)=><div key={`${c.source_id}-${c.employee_id}-${i}`}><strong>{c.employee_name}</strong><span>{c.title} · {timeText(c.starts_at)}–{new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(c.ends_at))}</span></div>)}</div>}
        <div className="ks-footer"><button type="button" className="ks-secondary" onClick={edit}><ArrowLeft size={16}/> Edit details</button><button type="button" className="ks-primary" disabled={!preview.can_create||buttonDisabled} onClick={()=>void handleConfirm()}>{loading?'Creating…':'Confirm & create meeting'}</button></div>
      </div>}
      {step==='created'&&created&&<div className="ks-content ks-success"><CheckCircle2 size={46}/><h3>Meeting created</h3><p>Meeting and participant calendar bookings were saved together.</p><strong>{created.title}</strong><p>{timeText(created.starts_at)} – {new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(created.ends_at))}</p><small>Meeting ID: {created.id}</small><div className="ks-footer"><button type="button" className="ks-secondary" onClick={onClose}>Close</button><button type="button" className="ks-primary" onClick={()=>onCreated(istDay(created.starts_at))}>View updated calendar →</button></div></div>}
    </section>
  </div>;
}
