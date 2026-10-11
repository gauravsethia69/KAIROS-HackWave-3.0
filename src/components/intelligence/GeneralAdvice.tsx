import { Lightbulb, Sparkles, ShieldCheck, ArrowRight, LoaderCircle, BookOpenText } from 'lucide-react';
import type { GeneralAdviceResult } from '../../ai/generalAdvice';
import './general-advice.css';

export function GeneralAdvice({ question, result, pending, onRetry }: {
  question: string; result: GeneralAdviceResult | null; pending: boolean; onRetry: () => void;
}) {
  const items = result?.status === 'enriched' ? result.advice : null;
  return <section className="kairos-general-advice" aria-labelledby="kairos-general-title">
    <header className="kairos-general-header">
      <div className="kairos-general-symbol"><Lightbulb size={26}/></div>
      <div className="kairos-general-heading"><div className="kairos-general-eyebrow"><Sparkles size={14}/> KAI · GENERAL STRATEGY</div>
        <h2 id="kairos-general-title">{items?.title || 'Your AI strategy guide'}</h2>
        <p>{question}</p></div>
      <span className="kairos-general-tag"><ShieldCheck size={14}/> ADVISORY</span>
    </header>
    {pending ? <div role="status" className="kairos-general-loading"><LoaderCircle className="kairos-general-spin" size={22}/><div><strong>Preparing your strategy…</strong><p>Groq is drafting practical recommendations, not querying SORYU's database.</p></div></div> : items ? <div className="kairos-general-content" role="region" aria-label="AI strategy response">
      <p className="kairos-general-lead">{items.introduction}</p>
      <div className="kairos-general-steps">{items.steps.map((item, i) => <article key={`${i}-${item.action}`} className="kairos-general-step"><span className="kairos-general-number">{String(i+1).padStart(2,'0')}</span><div><h3>{item.action}</h3><p>{item.why}</p></div></article>)}</div>
      {items.caution && <div className="kairos-general-note"><BookOpenText size={16}/><span>{items.caution}</span></div>}
      <p className="kairos-general-disclosure"><ShieldCheck size={15}/> General AI recommendations · No live revenue figures or company-specific performance claims · {result?.cached ? 'Cached answer' : 'Generated on request'}</p>
    </div> : <div className="kairos-general-unavailable" role="status">
      <p>{result?.status === 'off' ? 'Groq is disabled. No AI response was generated.' : result?.status === 'budget' ? 'The local Groq request budget is reached.' : result?.status === 'not_general' ? 'This question needs an authorized enterprise workspace rather than general advice.' : 'The AI answer is temporarily unavailable. No synthetic answer was substituted.'}</p>
      <button type="button" onClick={onRetry} disabled={pending}><Sparkles size={15}/> Try AI answer again <ArrowRight size={15}/></button>
    </div>}
  </section>;
}
