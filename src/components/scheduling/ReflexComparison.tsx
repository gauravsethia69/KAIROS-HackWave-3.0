/** KAIROS Reflex: decision support only. All actual writes remain in MeetingScheduler. */
import { ArrowRight, BrainCircuit, CalendarClock, ShieldCheck, Users } from 'lucide-react';
import './reflex-comparison.css';

export type ReflexCandidate = {
  label:string; starts_at:string; ends_at:string;rank:number;recorded_clear:boolean;
  truncated:boolean;affected_employee_count:number;recorded_overlap_count:number;
  overlap_participant_hours:number;conflicts:Array<{employee_id:string;employee_name:string;title:string;starts_at:string;ends_at:string}>;
  more_conflicts:boolean;notice:string;
};
export type ReflexResult = {
  status:'compared';read_only:true;source:string;time_zone:string;participants_count:number;
  candidates:ReflexCandidate[];
  task_context:{visible_open_tasks:number;estimated_backlog_hours:number;tasks_without_estimates:number;truncated:boolean;notice:string};
  warning:string;
};
const dateText=(iso:string)=>new Intl.DateTimeFormat('en-IN',{
  timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true,
}).format(new Date(iso));

export function ReflexComparison({data,onChoose}:{data:ReflexResult;onChoose:(startUTC:string)=>void}) {
  const ranked=[...data.candidates].sort((a,b)=>a.rank-b.rank);
  return <section className="kr-panel" aria-label="KAIROS Reflex alternatives">
    <div className="kr-heading"><BrainCircuit size={19}/><div><strong>KAIROS Reflex</strong><small>What-if coordination · read-only · recorded evidence</small></div></div>
    <p className="kr-caption">{data.candidates.length} hypothetical meeting times compared against accessible recorded bookings for {data.participants_count} participant{data.participants_count===1?'':'s'}. Ranked by fewer observed clashes, then proximity to the requested time.</p>
    <div className="kr-grid">{ranked.map(c=><article className="kr-option" key={c.starts_at}>
      <div className="kr-top"><span>#{c.rank} · {c.label}</span><span className={c.recorded_clear?'kr-clear':'kr-conflict'}>{c.recorded_clear?'No recorded clash':c.truncated?'Incomplete records':'Recorded clash'}</span></div>
      <h4><CalendarClock size={15}/>{dateText(c.starts_at)}</h4>
      <div className="kr-metrics"><span><Users size={13}/> {c.affected_employee_count} affected</span><span>{c.overlap_participant_hours.toFixed(2)} overlapping participant-hours</span></div>
      {c.conflicts.length>0 && <details><summary>Inspect {c.recorded_overlap_count} source overlap{c.recorded_overlap_count===1?'':'s'}</summary>
        <ul>{c.conflicts.map((v,i)=><li key={`${v.employee_id}:${v.starts_at}:${i}`}>{v.employee_name}: {v.title} ({dateText(v.starts_at)})</li>)}</ul>
        {c.more_conflicts&&<small>Some source overlaps are omitted here.</small>}
      </details>}
      <button type="button" onClick={()=>onChoose(c.starts_at)}><ArrowRight size={14}/> Use this time in form</button>
    </article>)}</div>
    <div className="kr-context"><ShieldCheck size={17}/><p><strong>Visible team task context:</strong> {data.task_context.visible_open_tasks} open tasks · {data.task_context.estimated_backlog_hours} estimated backlog hours · {data.task_context.tasks_without_estimates} tasks without estimates. {data.task_context.notice}</p></div>
    <p className="kr-warning">{data.warning}</p>
  </section>;
}
