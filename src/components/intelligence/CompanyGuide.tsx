import { BookOpenText, CheckCircle2, GraduationCap, Layers3, LoaderCircle, ShieldCheck, Sparkles, ArrowRight } from 'lucide-react';
import type { CompanyGuideData, CompanyGuideEnrichment } from '../../ai/companyGuide';
import './company-guide.css';

function Passage({ passage, summary }: {
  passage: CompanyGuideData['passages'][number]; summary?: string;
}) {
  const isProposed = passage.status === 'proposed' || /^proposed\b/i.test(passage.section);
  return <article className="company-guide-passage" data-atlas-page={passage.page}>
    <div className="company-guide-passage-top">
      <span className="company-guide-page">ATLAS · PAGE {String(passage.page).padStart(2, '0')}</span>
      <span className={`company-guide-status ${isProposed ? 'proposed' : 'reference'}`}>{isProposed ? 'PROPOSED · NOT POLICY' : 'REFERENCE'}</span>
    </div>
    <h3>{passage.title}</h3>
    <p className="company-guide-section">{passage.section}</p>
    {summary && <p className="company-guide-summary">{summary}</p>}
    {!summary && <p className="company-guide-original">{passage.text}</p>}
    {summary && <details><summary>Inspect original Atlas excerpt</summary><p>{passage.text}</p></details>}
    <div className="company-guide-source"><BookOpenText size={13}/>{passage.citation}</div>
  </article>;
}

export function CompanyGuide({guide, ai, aiPending, onExplain}: {
  guide: CompanyGuideData;
  ai: CompanyGuideEnrichment | null;
  aiPending: boolean;
  onExplain: () => void;
}) {
  const match = new Map(guide.passages.map(p => [p.id, p]));
  // Extra frontend safeguard against cross-source or invented references.
  const summaries = (ai?.status === 'enriched' ? ai.items : []).filter(
    s => match.has(s.chunk_id) && match.get(s.chunk_id)?.citation === s.citation &&
      match.get(s.chunk_id)?.status === s.status && match.get(s.chunk_id)?.page === s.page
  );
  return <section className="company-guide" aria-labelledby="company-guide-heading">
    <div className="company-guide-hero">
      <div className="company-guide-logo"><GraduationCap size={27}/></div>
      <div>
        <div className="company-guide-eyebrow"><Sparkles size={14}/> YOUR QUESTION BECAME A KNOWLEDGE GUIDE</div>
        <h2 id="company-guide-heading">{guide.title}</h2>
        <p>{guide.subtitle}</p>
      </div>
      <span className="company-guide-trusted"><ShieldCheck size={14}/> SOURCED</span>
    </div>
    <div className="company-guide-intro"><Layers3 size={19}/><div><strong>How SORYU works · Document-grounded answers</strong><p>This guide explains company references. For your actual manager, assignments, schedules and current records, ask KAIROS to use the authenticated enterprise workspace.</p></div></div>
    {guide.status === 'not_found' ? <p className="company-guide-empty">The Atlas has no matching guidance. Try a more specific company question; KAIROS won't invent policies.</p> : <>
      <div className="company-guide-ai-choice" aria-label="Optional Groq explanation">
        <div className="company-guide-ai-choice-copy">
          <span className="company-guide-ai-choice-kicker"><Sparkles size={15}/> OPTIONAL · GROQ AI</span>
          <strong>Would you like KAI to explain how SORYU works?</strong>
          <p>Get a plain-English, source-cited walkthrough of the company. Atlas references below are always available without using Groq tokens.</p>
          <span className="company-guide-ai-cost">Groq is called only when you press the button. Each uncached request may consume tokens.</span>
        </div>
        <div className="company-guide-ai-actions">
          <button type="button" className="company-guide-explain-button" onClick={onExplain}
            disabled={aiPending || guide.passages.length === 0} aria-busy={aiPending}>
            {aiPending ? <><LoaderCircle size={17} className="company-guide-spin"/> Writing your explanation…</> :
              <><Sparkles size={17}/>{summaries.length ? 'Show AI explanation again' : ai ? 'Try AI explanation again' : 'Explain with AI'}<ArrowRight size={16}/></>}
          </button>
          <a className="company-guide-atlas-link" href="#kairos-atlas-sources">Continue with Atlas only</a>
        </div>
      </div>
      <div className="company-guide-ai-bar" role="status" aria-live="polite">
        <Sparkles size={16}/>
        {aiPending ? <>Groq is writing an explanation from these cited Atlas references. You can already read the originals below.</> :
          summaries.length ? <><CheckCircle2 size={15}/> AI explanation is ready, grounded in {summaries.length} Atlas excerpts.</> :
          ai?.status === 'enriched' ? <>Groq answered, but its source references did not match the retrieved Atlas passages. Unverified text is not shown.</> :
          ai?.status === 'budget' ? <>The configured AI request budget is reached. The Atlas guide still works.</> :
          ai?.status === 'off' ? <>Groq explanations are disabled in backend settings. Atlas remains available.</> :
          ai?.status === 'fallback' ? <>Groq could not produce a verified explanation this time. Atlas references remain available.</> :
          <>You are viewing the Atlas-only guide. No Groq call has been made for this question.</>}
      </div>
      {summaries.length > 0 && <section className="company-guide-ai-answer" aria-label="Groq onboarding explanation">
        <h3><Sparkles size={20}/> KAI's company walkthrough</h3>
        <p className="company-guide-ai-answer-note">A plain-English guide, based only on the cited reference passages. Proposed procedures are not approved policy.</p>
        {summaries.map((item, index) => {
          const source = match.get(item.chunk_id)!;
          return <article className="company-guide-ai-point" key={item.chunk_id}>
            <span className="company-guide-ai-point-number">{String(index + 1).padStart(2, '0')}</span>
            <div><h4>{source.title}</h4><p>{item.summary}</p><span className="company-guide-ai-citation"><BookOpenText size={13}/>{source.citation}{source.status === 'proposed' ? ' · PROPOSED, NOT POLICY' : ''}</span></div>
          </article>;
        })}
      </section>}
      <h3 id="kairos-atlas-sources" className="company-guide-group-heading">What the company Atlas says <span>{guide.passages.length} excerpts · {guide.source}</span></h3>
      <div className="company-guide-grid">{guide.passages.map(p => <Passage key={p.id} passage={p}/>)}</div>
    </>}
    <p className="company-guide-footer"><ShieldCheck size={15}/>{guide.authority} Procedures marked <strong>proposed</strong> are not approved company policy.</p>
  </section>;
}
