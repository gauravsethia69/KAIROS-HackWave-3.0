import { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, BookOpen, CheckCircle2, ChevronDown, FileSearch, ShieldAlert } from 'lucide-react';
import { apiRequest } from '../../lib/api';
import type { EnterpriseResponse, EnterpriseEntity } from '../../ai/enterprise';
import './enterprise-evidence.css';
import './enterprise-answer.css';

type Detail = {label:string;text:string};
type Claim = EnterpriseResponse['claims'][number];

/** Distinguish individual evidence references from visual record identities.
 * Multiple field citations to the same row collapse to ONE chip, but every
 * underlying evidence ID remains available within the drill-down drawer.
 */
export function recordIdentity(id:string):string {
  const fields=id.split(':');
  return fields[0]==='db' && fields.length===4 ? fields.slice(0,3).join(':') : id;
}
export function groupedReferences(ids:string[]):string[][] {
  const grouped=new Map<string,string[]>();
  for(const id of ids){const k=recordIdentity(id);const bucket=grouped.get(k)||[];if(!bucket.includes(id))bucket.push(id);grouped.set(k,bucket);}
  return [...grouped.values()];
}
/** Server-grounded evidence cards: concise answer, contextual action,
 * and details on demand. Authenticated evidence endpoint is the only drilldown.
 */
export function EnterpriseAnswerView({result,onSelect}:{result:EnterpriseResponse;onSelect:(entity:EnterpriseEntity)=>void}) {
  const [detail,setDetail]=useState<Detail|null>(null);
  const [expanded,setExpanded]=useState<string[]|null>(null);
  const [busyId,setBusyId]=useState<string|null>(null);
  const byId=useMemo(()=>new Map(result.evidence.map(e=>[e.id,e])),[result]);
  const factual=result.claims.filter(c=>c.kind!=='proposed_action');
  const actions=result.claims.filter(c=>c.kind==='proposed_action');
  const highlighted=factual.slice(0,3);
  const additional=factual.slice(3);
  const clarity=result.intent.clarification;
  useEffect(()=>{setDetail(null);setExpanded(null);},[result]);
  async function showEvidence(id:string) {
    const item=byId.get(id);if(!item)return;
    setBusyId(id);
    try {
      if(item.navigation.kind==='knowledge_document'&&item.navigation.document_id){
        const response=await apiRequest<{metadata:{title:string};body:string}>(`/api/intelligence/knowledge/documents/${encodeURIComponent(item.navigation.document_id)}`);
        setDetail({label:response.metadata.title,text:response.body});
      }else{
        const response=await apiRequest<{value:unknown}>(`/api/intelligence/evidence/${encodeURIComponent(id)}`);
        setDetail({label:item.title,text:JSON.stringify(response.value,null,2)});
      }
    } catch(err){setDetail({label:item.title,text:err instanceof Error?err.message:'Evidence unavailable.'});}
    finally{setBusyId(null);}
  }
  function EvidenceLinks({claim}:{claim:Claim}) {
    const groups=groupedReferences(claim.evidence_ids);
    return groups.length?<div className="enterprise-sources">{groups.slice(0,3).map(ids=>{
      const pref=ids.find(id=>id.endsWith(':record'))||ids[0];
      const item=byId.get(pref);
      return <button key={recordIdentity(pref)} type="button" title={`${ids.length} verified source field(s)`} onClick={()=>setExpanded(ids)}><BookOpen size={12}/>{item?.title||'Verified source'}<ArrowUpRight size={11}/></button>;
    })}{groups.length>3&&<button className="enterprise-more-sources" onClick={()=>setExpanded(groups.flat())}>+{groups.length-3} record sources</button>}</div>:null;
  }
  function Card({claim,index}:{claim:Claim;index:number}) {
    return <article className={`enterprise-claim ${claim.kind}`} key={`${index}-${claim.kind}`}>
      <div className="enterprise-claim-head">{claim.kind==='uncertainty'?<ShieldAlert size={15}/>:<CheckCircle2 size={15}/>}<span>{claim.kind.replace('_',' ')}</span></div>
      <p>{claim.text}</p><EvidenceLinks claim={claim}/>
    </article>;
  }
  return <section className="enterprise-evidence" aria-label="Enterprise answer and source records">
    <div className="enterprise-evidence-heading"><FileSearch size={20}/><div><strong>KAIROS verified answer</strong><small>{result.intelligence?.status === 'enriched' ? 'Groq-ranked · verified SORYU records · evidence-linked' : 'Authenticated SORYU records · evidence-linked · deterministic'}</small></div></div>
    {clarity&&<div className="enterprise-clarification"><strong>{clarity.question}</strong><div className="enterprise-choice-list">{clarity.candidates.map(candidate=><button key={`${candidate.entity.entity_type}:${candidate.entity.entity_id}`} onClick={()=>onSelect(candidate.entity)}>{candidate.label}<ArrowUpRight size={13}/></button>)}</div>{!!clarity.suggestions.length&&<p>Try: {clarity.suggestions.join(' · ')}</p>}</div>}
    {(result.status==='unsupported'||result.status==='not_found')&&!factual.length&&<p role="status">No matching verified records were found. Refine the employee, client or date.</p>}
    {!!highlighted.length&&<div className="enterprise-claims enterprise-summary">{highlighted.map((c,i)=><Card claim={c} index={i} key={`${i}-highlight`}/>)}</div>}
    {!!actions.length&&<div className="enterprise-action-strip"><strong>Suggested next step</strong><p>{actions[0].text}</p><EvidenceLinks claim={actions[0]}/></div>}
    {(additional.length>0||actions.length>1)&&<details className="enterprise-more-findings"><summary>Inspect {additional.length+(actions.length-1)} additional verified finding(s) <ChevronDown size={14}/></summary><div className="enterprise-claims">{additional.map((c,i)=><Card claim={c} index={i+3} key={`${i}-additional`}/>)}{actions.slice(1).map((c,i)=><Card claim={c} index={i+factual.length} key={`${i}-action`}/>)}</div></details>}
    {!!result.limitations.length&&<details className="enterprise-limitations"><summary>Data limitations <ChevronDown size={14}/></summary>{result.limitations.map((s,i)=><p key={i}>{s}</p>)}</details>}
    {expanded&&<div className="enterprise-detail"><div className="enterprise-detail-head"><strong>Evidence references · {expanded.length} field(s)</strong><button onClick={()=>{setExpanded(null);setDetail(null)}}>Close</button></div><p className="enterprise-detail-hint">Deduplicated by underlying record. Each original field citation can still be inspected.</p><div className="enterprise-sources">{expanded.map(id=><button key={id} disabled={busyId===id} onClick={()=>void showEvidence(id)}>{byId.get(id)?.field||'record'} · {byId.get(id)?.title||id} <ArrowUpRight size={11}/></button>)}</div></div>}
    {detail&&<div className="enterprise-detail"><div className="enterprise-detail-head"><strong>{detail.label}</strong><button onClick={()=>setDetail(null)}>Close</button></div><pre>{detail.text}</pre></div>}
  </section>;
}
