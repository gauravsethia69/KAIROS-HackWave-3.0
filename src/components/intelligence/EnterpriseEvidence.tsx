import { useState } from 'react';
import { ArrowUpRight, BookOpen, CheckCircle2, ChevronDown, FileSearch, ShieldAlert } from 'lucide-react';
import { apiRequest } from '../../lib/api';
import type { EnterpriseResponse, EnterpriseEntity } from '../../ai/enterprise';
import './enterprise-evidence.css';

type Detail = { label: string; text: string };

/** Server-grounded, read-only evidence viewer. No local synthetic claims. */
export function EnterpriseEvidence({ result, onSelect }: { result: EnterpriseResponse; onSelect: (entity: EnterpriseEntity) => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const evidenceById = new Map(result.evidence.map(e => [e.id,e]));
  const clarity = result.intent.clarification;
  async function showEvidence(id: string) {
    const item = evidenceById.get(id);
    if (!item) return;
    setBusyId(id);
    try {
      if (item.navigation.kind === 'knowledge_document' && item.navigation.document_id) {
        const response = await apiRequest<{metadata: {title:string}; body: string}>(`/api/intelligence/knowledge/documents/${encodeURIComponent(item.navigation.document_id)}`);
        setDetail({label:response.metadata.title, text:response.body});
      } else {
        const response = await apiRequest<{value: unknown}>(`/api/intelligence/evidence/${encodeURIComponent(id)}`);
        setDetail({label:item.title, text:JSON.stringify(response.value,null,2)});
      }
    } catch (err) {
      setDetail({label:item.title, text:err instanceof Error ? err.message : 'The evidence record could not be opened.'});
    } finally { setBusyId(null); }
  }
  return <section className="enterprise-evidence" aria-label="Enterprise investigation and sources">
    <div className="enterprise-evidence-heading"><FileSearch size={19}/><div><strong>SORYU investigation</strong><small>Verified database records and authored company references · deterministic, no Groq</small></div></div>
    {clarity && <div className="enterprise-clarification"><strong>{clarity.question}</strong><div className="enterprise-choice-list">
      {clarity.candidates.map(candidate => <button key={`${candidate.entity.entity_type}:${candidate.entity.entity_id}`} onClick={() => onSelect(candidate.entity)}>{candidate.label}<ArrowUpRight size={13}/></button>)}
    </div>{clarity.suggestions.length > 0 && <p>Try: {clarity.suggestions.join(' · ')}</p>}</div>}
    {(result.status === 'unsupported' || result.status === 'not_found') && <p role="status">No supported, grounded workspace could be built for this request. Try a specific client, project, task or employee ID.</p>}
    {!!result.claims.length && <div className="enterprise-claims">{result.claims.slice(0,18).map((claim,i) => <article key={`${i}-${claim.kind}`} className={`enterprise-claim ${claim.kind}`}>
      <div className="enterprise-claim-head">{claim.kind === 'uncertainty' ? <ShieldAlert size={15}/> : <CheckCircle2 size={15}/>}<span>{claim.kind.replace('_',' ')}</span></div>
      <p>{claim.text}</p>
      {!!claim.evidence_ids.length && <div className="enterprise-sources">{claim.evidence_ids.slice(0,5).map(id => <button key={id} type="button" disabled={busyId === id} title={id} onClick={() => void showEvidence(id)}><BookOpen size={12}/>{evidenceById.get(id)?.title || id}<ArrowUpRight size={11}/></button>)}{claim.evidence_ids.length > 5 && <small>+{claim.evidence_ids.length - 5} additional source records</small>}</div>}
    </article>)}</div>}
    {result.claims.length > 18 && <p className="enterprise-claim-overflow">Showing 18 of {result.claims.length} grounded claims. Narrow the question to view a smaller evidence set.</p>}
    {!!result.limitations.length && <details className="enterprise-limitations"><summary>Data limitations <ChevronDown size={14}/></summary>{result.limitations.map((s,i)=><p key={i}>{s}</p>)}</details>}
    {detail && <div className="enterprise-detail"><div className="enterprise-detail-head"><strong>{detail.label}</strong><button type="button" onClick={()=>setDetail(null)}>Close</button></div><pre>{detail.text}</pre></div>}
  </section>;
}
