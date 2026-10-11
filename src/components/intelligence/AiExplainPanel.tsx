import { BookOpenText, CheckCircle2, CircleHelp, Coins, LoaderCircle, Sparkles } from 'lucide-react';
import type { WorkspaceExplanation, AITokenUsage } from '../../ai/aiExplain';
import './ai-explain.css';

export function AiExplainPanel({ ai, busy, onExplain, usage, onUsage }: {
  ai: WorkspaceExplanation | null; busy: boolean; onExplain: () => void;
  usage: AITokenUsage | null; onUsage: () => void;
}) {
  const count = usage ? Object.values(usage.by_feature).reduce((sum, row) => sum + row.input_tokens + row.output_tokens, 0) : 0;
  return <section className="kairos-ai-explain" aria-label="Optional Groq explanation">
    <div className="kairos-ai-explain-top">
      <div><span className="kairos-ai-label"><Sparkles size={15}/> AI ON DEMAND · FREE-FIRST</span>
        <h3>Explain the verified findings</h3>
        <p>Your adaptive workspace is already ready. Groq runs only if you request an explanation.</p></div>
      <button className="kairos-ai-trigger" onClick={onExplain} disabled={busy}>
        {busy ? <><LoaderCircle size={16} className="kairos-ai-spin"/> Explaining…</> : <><Sparkles size={16}/> Explain with AI</>}
      </button>
    </div>
    {ai && <div className="kairos-ai-answer" aria-live="polite">
      {ai.status === 'enriched' ? <>
        <p className="kairos-ai-callout"><CheckCircle2 size={16}/> Groq explanation · verified evidence linked · {ai.cached ? 'reused without a new call' : 'on-demand response'}</p>
        {ai.points.map((item, index) => <article key={`${item.claim_index}-${index}`} className="kairos-ai-point">
          <strong>Verified database finding</strong><p>{item.finding}</p>
          <strong>Groq explanation</strong><p>{item.explanation}</p>
          <small>{item.evidence_ids.length} server-verified evidence ID(s) · Confirm with original records below</small>
        </article>)}
        {ai.atlas_sources.length > 0 && <details className="kairos-ai-sources"><summary><BookOpenText size={15}/> Atlas passages provided to Groq</summary>
          {ai.atlas_sources.map(s => <p key={s.id}><strong>Page {s.page} · {s.source_id} · {s.status === 'proposed' ? 'PROPOSED / NOT POLICY' : 'REFERENCE'}</strong><span>{s.text}</span></p>)}
        </details>}
      </> : <p className="kairos-ai-callout"><CircleHelp size={16}/>
        {ai.status === 'off' ? 'Groq is turned off. Your verified database workspace remains available.' :
         ai.status === 'budget' ? 'Local AI request budget reached. No new Groq call was made.' :
         'AI explanation is unavailable. No unsupported explanation was substituted.'}</p>}
    </div>}
    <div className="kairos-ai-meter"><button onClick={onUsage}><Coins size={14}/> {usage ? 'Refresh' : 'View'} process token usage</button>
      {usage && <span>{count.toLocaleString()} recorded tokens across features · process-local; confirm actual usage in Groq Console</span>}
    </div>
  </section>;
}
