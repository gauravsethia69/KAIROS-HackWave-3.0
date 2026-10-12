/** KAIROS Reflex: presentation only. No endpoint calls, booking, or new decisions. */
import {
  ArrowRight, BrainCircuit, CalendarClock, CheckCircle2, ChevronDown,
  Clock3, GitCompareArrows, Info, ShieldCheck, Users, AlertTriangle,
} from 'lucide-react';
import './reflex-comparison.css';

// These contracts intentionally stay identical to Pass 13A's backend response.
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
  timeZone:'Asia/Kolkata',weekday:'short',day:'2-digit',month:'short',year:'numeric',
}).format(new Date(iso));
const timeText=(iso:string)=>new Intl.DateTimeFormat('en-IN',{
  timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:true,
}).format(new Date(iso));
const durationMinutes=(start:string,end:string)=>Math.max(0,Math.round((new Date(end).getTime()-new Date(start).getTime())/60000));

/** Render a non-predictive overlap comparison. These bars summarize *recorded* overlap hours only. */
function overlapPercent(candidate:ReflexCandidate,participants:number):number {
  const totalHours=durationMinutes(candidate.starts_at,candidate.ends_at)/60*Math.max(1,participants);
  if(!Number.isFinite(totalHours)||totalHours<=0)return 0;
  return Math.max(0,Math.min(100,(candidate.overlap_participant_hours/totalHours)*100));
}

export function ReflexComparison({data,onChoose}:{data:ReflexResult;onChoose:(startUTC:string)=>void}) {
  // Rank comes from the server. The frontend never invents or recalculates a winner.
  const ranked=[...data.candidates].sort((a,b)=>a.rank-b.rank);
  const observedOverlap=ranked.reduce((sum,c)=>sum+c.recorded_overlap_count,0);
  const hasIncomplete=ranked.some(c=>c.truncated||c.more_conflicts)||data.task_context.truncated;
  const cleanCount=ranked.filter(c=>c.recorded_clear&&!c.truncated).length;

  return <section className="kr-panel" aria-label="KAIROS Reflex alternatives" data-testid="reflex-polished">
    <header className="kr-hero">
      <div className="kr-hero-main">
        <div className="kr-hero-symbol" aria-hidden="true"><BrainCircuit size={24}/></div>
        <div className="kr-hero-title">
          <div className="kr-eyebrow">KAIROS REFLEX <span aria-hidden="true">/</span> DECISION STUDIO</div>
          <h3>Find a better time, before committing.</h3>
          <p>Three what-if schedules, compared against authorized calendar records. Every option still needs a fresh booking review.</p>
        </div>
      </div>
      <div className="kr-hero-flags"><span><ShieldCheck size={13}/> Read-only simulation</span><span><Clock3 size={13}/> IST (UTC+5:30)</span></div>
    </header>

    <div className="kr-insights" aria-label="Comparison overview">
      <div className="kr-insight"><strong>{ranked.length.toString().padStart(2,'0')}</strong><span>Time options</span></div>
      <div className="kr-insight"><strong>{data.participants_count}</strong><span>Participants checked</span></div>
      <div className="kr-insight"><strong>{cleanCount}</strong><span>Without recorded clashes*</span></div>
      <div className="kr-insight"><strong>{observedOverlap}</strong><span>Recorded overlaps across options</span></div>
    </div>

    <div className="kr-section-heading">
      <div><GitCompareArrows size={17}/><h4>Compare the possibilities</h4></div>
      <small>Ranked by fewer observed clashes, then proximity to your requested time</small>
    </div>

    {ranked.length===0 && <p className="kr-empty" role="status">No comparable time options were returned. Nothing has been changed.</p>}
    <div className="kr-grid">
      {ranked.map((c,index)=>{
        const incomplete=c.truncated||c.more_conflicts;
        const clear=c.recorded_clear&&!c.truncated;
        const tone=incomplete?'limited':clear?'clear':'clash';
        const stateText=incomplete?'Incomplete conflict evidence':clear?'No recorded clash':'Recorded conflict';
        const overlap=overlapPercent(c,data.participants_count);
        return <article className={`kr-option kr-option--${tone} ${index===0?'kr-option--first':''}`} key={`${c.starts_at}:${c.rank}`} aria-label={`Rank ${c.rank}, ${c.label}, ${stateText}`}>
          <div className="kr-topline">
            <span className="kr-rank">OPTION {String(c.rank).padStart(2,'0')}</span>
            {index===0&&<span className="kr-first">First to review</span>}
          </div>
          <p className="kr-option-label">{c.label}</p>
          <div className="kr-date"><CalendarClock size={18}/><time dateTime={c.starts_at}>{dateText(c.starts_at)}</time></div>
          <div className="kr-time"><time dateTime={c.starts_at}>{timeText(c.starts_at)}</time><ArrowRight size={14} aria-hidden="true"/><time dateTime={c.ends_at}>{timeText(c.ends_at)}</time></div>
          <p className="kr-duration">{durationMinutes(c.starts_at,c.ends_at)} minutes · Asia/Kolkata</p>

          <div className={`kr-state kr-state--${tone}`}>
            {tone==='clear'?<CheckCircle2 size={16}/>:<AlertTriangle size={16}/>}
            <strong>{stateText}</strong>
          </div>
          <div className="kr-impact-top"><span>Observed overlap load</span><strong>{c.overlap_participant_hours.toFixed(2)} participant-h</strong></div>
          <div className="kr-track" role="img" aria-label={`${overlap.toFixed(0)} percent of total participant meeting time has recorded overlaps`}>
            <span className={`kr-track-fill kr-track-fill--${tone}`} style={{width:`${overlap}%`}}/>
          </div>
          <div className="kr-metrics">
            <span><Users size={14}/>{c.affected_employee_count} affected participant{c.affected_employee_count===1?'':'s'}</span>
            <span><GitCompareArrows size={14}/>{c.recorded_overlap_count} overlap{c.recorded_overlap_count===1?'':'s'}</span>
          </div>
          {c.conflicts.length>0?<details className="kr-evidence">
            <summary><span>Inspect recorded conflicts</span><ChevronDown size={15} aria-hidden="true"/></summary>
            <ul>{c.conflicts.map((v,i)=><li key={`${v.employee_id}:${v.starts_at}:${i}`}>
              <strong>{v.employee_name}</strong><span>{v.title}</span><small>{dateText(v.starts_at)}, {timeText(v.starts_at)} – {timeText(v.ends_at)}</small>
            </li>)}</ul>
            {c.more_conflicts&&<p className="kr-evidence-note">Additional overlaps were omitted from this preview.</p>}
          </details>:<p className="kr-no-evidence"><Info size={13}/> No overlap details in the accessible preview.</p>}
          {incomplete&&<p className="kr-limited"><AlertTriangle size={13}/> Conflict records may be incomplete for this option.</p>}
          <button className="kr-apply" type="button" onClick={()=>onChoose(c.starts_at)} aria-label={`Use ${c.label} in the meeting form, without booking`}>
            Use this time in form <ArrowRight size={16}/>
          </button>
        </article>;
      })}
    </div>

    <div className="kr-context"><span className="kr-context-icon"><Users size={18}/></span><div>
      <strong>Team workload context <span>· not calendar commitments</span></strong>
      <p><b>{data.task_context.visible_open_tasks}</b> visible open tasks <span aria-hidden="true">·</span> <b>{data.task_context.estimated_backlog_hours}</b> estimated backlog hours <span aria-hidden="true">·</span> <b>{data.task_context.tasks_without_estimates}</b> without estimates</p>
      <small>{data.task_context.notice}</small>
    </div></div>

    <footer className="kr-footer">
      <div><ShieldCheck size={18}/><p><strong>Nothing has been booked.</strong> Applying an option fills the original meeting form; the existing review and explicit confirmation are still required.</p></div>
      <p className="kr-warning">{data.warning}{hasIncomplete?' Some comparison records were incomplete.':''} *No recorded clash does not establish availability.</p>
    </footer>
  </section>;
}
