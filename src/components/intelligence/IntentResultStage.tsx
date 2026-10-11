import { Activity, ArrowDown, ArrowUpRight, BriefcaseBusiness, CalendarClock, CheckCircle2, CircleHelp, ClipboardList, DatabaseZap, FolderKanban, Layers3, Lightbulb, ScanSearch, ShieldAlert, Sparkles, UsersRound } from 'lucide-react';
import type { EnterpriseResponse } from '../../ai/enterprise';
import { intentAppearance, intentPrimaryClaim, intentWorkspaceLayers } from './intentPresentation';
import './intent-result-stage.css';

const iconByKind = {
  meeting: CalendarClock,
  usage: Activity,
  project: FolderKanban,
  support: ShieldAlert,
  people: UsersRound,
  executive: BriefcaseBusiness,
  lookup: ScanSearch,
};

/** Primary intent-to-interface result. All substantive findings come verbatim from the API. */
export function IntentResultStage({result, functionalView, visibleWidgetTitles, onWorkspace, onEvidence}:{
  result:EnterpriseResponse;
  functionalView:string | null;
  visibleWidgetTitles:string[];
  onWorkspace:()=>void;
  onEvidence:()=>void;
}) {
  const appearance = intentAppearance(result);
  const Icon = iconByKind[appearance.kind];
  const claim = intentPrimaryClaim(result);
  const layers = functionalView ? intentWorkspaceLayers(result,functionalView) : visibleWidgetTitles;
  const needsClarification = result.status==='clarification' || Boolean(result.intent.clarification);
  const unresolved = result.status==='unsupported' || result.status==='not_found';
  const hasWorkspace = Boolean(functionalView || visibleWidgetTitles.length);
  return <section className={`intent-result-stage intent-kind-${appearance.kind}`} aria-labelledby="intent-result-heading" data-intent={result.intent.name} data-result-status={result.status}>
    <div className="intent-result-head">
      <div className="intent-result-icon" aria-hidden="true"><Icon size={25}/></div>
      <div className="intent-result-title-block">
        <div className="intent-result-kicker"><Sparkles size={14}/><span>YOUR REQUEST BECAME AN INTERFACE</span><span className="intent-result-divider"/><span>{appearance.eyebrow}</span></div>
        <h2 id="intent-result-heading">{needsClarification?'One detail needed':unresolved?'No verified match':appearance.title}</h2>
        <p>{result.title}</p>
      </div>
      <span className={`intent-result-status ${result.status}`}>{needsClarification?<CircleHelp size={13}/>:unresolved?<ShieldAlert size={13}/>:<CheckCircle2 size={13}/>} {needsClarification?'CLARIFY':result.status==='ready'?'COMPOSED':result.status.toUpperCase()}</span>
    </div>
    <div className="intent-result-body">
      <div className="intent-result-insight">
        <span className="intent-result-micro">{needsClarification?'NEEDS YOUR INPUT':claim?'KEY FINDING FROM AUTHORIZED DATA':'CURRENT RESULT'}</span>
        <p className="intent-result-primary" role="status">{claim || (needsClarification?result.intent.clarification?.question:unresolved?'No verified records matched this request. Refine the query to try again.':'An authenticated workspace was composed. Open the interface to inspect the supporting records.')}</p>
        <div className="intent-result-provenance"><DatabaseZap size={14}/> {result.source==='deterministic-enterprise'?'SORYU authenticated intelligence · not generated demo data':'Source information unavailable'}{result.evidence.length>0?` · ${result.evidence.length} evidence reference${result.evidence.length===1?'':'s'}`:''}</div>
      </div>
      <div className="intent-result-composition">
        <div className="intent-composition-caption"><Layers3 size={15}/> INTERFACE SELECTED FOR YOUR GOAL</div>
        <strong>{appearance.interfaceName}</strong>
        <p>{appearance.purpose}</p>
        {layers.length>0?<ul>{layers.map(label=><li key={label}><CheckCircle2 size={13}/>{label}</li>)}</ul>:<div className="intent-result-awaiting">{needsClarification?'Choose a specific record in the clarification below.':'No interactive components were returned for this request.'}</div>}
      </div>
    </div>
    <div className="intent-result-actions">
      <button type="button" className="intent-open-workspace" onClick={onWorkspace} disabled={!hasWorkspace}>Open adaptive workspace <ArrowDown size={16}/></button>
      <button type="button" className="intent-evidence-jump" onClick={onEvidence} disabled={!result.evidence.length&&!result.claims.length}>Inspect findings & sources <ArrowUpRight size={15}/></button>
      <span className="intent-result-verified"><ClipboardList size={13}/> {layers.length} visible workspace section{layers.length===1?'':'s'}</span>
    </div>
    {result.explanations.length>0&&<details className="intent-reasoning"><summary><Lightbulb size={15}/> Why did KAIROS build this interface? <span>View selection reasoning</span></summary><ol>{result.explanations.map((item,index)=><li key={`${index}-${item}`}>{item}</li>)}</ol></details>}
  </section>;
}
