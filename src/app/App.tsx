import { useCallback, useEffect, useRef, useState } from 'react';
import type { User } from '@supabase/supabase-js';
import { ArrowDownUp, ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown, Command, Database, FolderKanban, HelpCircle, LayoutDashboard, RotateCcw, Save, Sparkles, TrendingDown, UserRound, X } from 'lucide-react';
import { Kai } from '../components/assistant/Kai';
import type { KaiState } from '../components/assistant/Kai';
import { Workspace } from '../components/layout/Workspace';
import { Account } from '../components/layout/Account';
import { initialPlan, planLocally, transform } from '../ai/planner';
import { planEnterprise, adaptEnterprisePlan, enterpriseDataset } from '../ai/enterprise';
import type { EnterpriseResponse, EnterpriseEntity } from '../ai/enterprise';
import { EnterpriseEvidence } from '../components/intelligence/EnterpriseEvidence';
import { EnterpriseAnswerView } from '../components/intelligence/EnterpriseAnswerView';
import { IntentResultStage } from '../components/intelligence/IntentResultStage';
import { FunctionalWorkspace, selectedFunctionalView } from '../components/intelligence/FunctionalWorkspace';
import { MeetingScheduler } from '../components/scheduling/MeetingScheduler';
import { demoData, DEMO_DATE } from '../data/demo';
import { scopeData } from '../data/selectors';
import { loadDataset, savedWorkspaces, saveWorkspace } from '../data/repository';
import { supabase } from '../lib/supabase';
import type { WorkspacePlan } from '../types/workspace';
import { SidebarSakuraBranches } from '../components/KairosDecorations';
import { KairosHeroScene } from '../components/KairosHeroScene';
import { BookOpenText } from 'lucide-react';
import { fetchCompanyGuide, explainCompanyGuide, isCompanyKnowledgeQuestion } from '../ai/companyGuide';
import type { CompanyGuideData, CompanyGuideEnrichment } from '../ai/companyGuide';
import { CompanyGuide } from '../components/intelligence/CompanyGuide';
import { GeneralAdvice } from '../components/intelligence/GeneralAdvice';
import { fetchGeneralAdvice, isGeneralAdviceQuestion } from '../ai/generalAdvice';
import type { GeneralAdviceResult } from '../ai/generalAdvice';
import { AiExplainPanel } from '../components/intelligence/AiExplainPanel';
import { explainWorkspace, fetchAIUsage } from '../ai/aiExplain';
import type { WorkspaceExplanation, AITokenUsage } from '../ai/aiExplain';
import '../styles/kairos-sakura-theme.css';
const suggestions = [
  { icon: CalendarDays, label: 'Walk into your next meeting prepared', detail: 'Client context, talking points & next steps', input: "Prepare for an OrbitPay client meeting.", tag: 'MEETING PREP' },
  { icon: TrendingDown, label: 'Find the story behind the numbers', detail: 'Usage trends, evidence & possible causes', input: "Investigate product usage for OrbitPay.", tag: 'USAGE INVESTIGATION' },
  { icon: FolderKanban, label: 'Get your projects back on track', detail: 'Delivery gaps, blockers & responsible owners', input: 'Review delayed projects for Atlas Media Group.', tag: 'PROJECT REVIEW' },
];
export default function App({ initialPrompt = '' }: { initialPrompt?: string }) {
  const [plan, setPlan] = useState<WorkspacePlan>(initialPlan);
  const [input, setInput] = useState(initialPrompt);
  const [state, setState] = useState<KaiState>('idle');
  const [data, setData] = useState(demoData);
  const [loading, setLoading] = useState(false);
  const [dataError, setDataError] = useState('');
  const [user, setUser] = useState<User | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [meetingComposer, setMeetingComposer] = useState(false);
  const [connected, setConnected] = useState(false);
  const [live, setLive] = useState(false);
  const [source, setSource] = useState('Deterministic planner');
  const [enterprise, setEnterprise] = useState<EnterpriseResponse | null>(null);
  const [companyGuide, setCompanyGuide] = useState<CompanyGuideData | null>(null);
  const [companyGuideAI, setCompanyGuideAI] = useState<CompanyGuideEnrichment | null>(null);
  const [companyGuideBusy, setCompanyGuideBusy] = useState(false); // Atlas lookup
  const [companyGuideAIBusy, setCompanyGuideAIBusy] = useState(false); // only after explicit user action
  const [generalAdviceQuestion, setGeneralAdviceQuestion] = useState('');
  const [generalAdviceAnswer, setGeneralAdviceAnswer] = useState<GeneralAdviceResult | null>(null);
  const [generalAdviceBusy, setGeneralAdviceBusy] = useState(false);
  const companyGuideQuestion = useRef('');
  const [workspaceAI, setWorkspaceAI] = useState<WorkspaceExplanation | null>(null);
  const [workspaceAIBusy, setWorkspaceAIBusy] = useState(false);
  const [aiUsage, setAIUsage] = useState<AITokenUsage | null>(null);
  const latestEnterpriseSelection = useRef<EnterpriseEntity | undefined>(undefined);
  const enterpriseToken = useRef<string | null>(null);
  const previousEnterprisePrompt = useRef('');
  const [notice, setNotice] = useState('');
  const [completed, setCompleted] = useState(new Set<string>());
  const [saved, setSaved] = useState<Awaited<ReturnType<typeof savedWorkspaces>>>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [explain, setExplain] = useState(false);
  const [resultRevision, setResultRevision] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const evidenceRef = useRef<HTMLDivElement>(null);
  const commandRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef(0);
  const dataRequestRef = useRef(0);
  const inFlight = useRef(false);
  const busy = state === 'understanding' || state === 'composing';
  const jumpTo = (target: HTMLElement | null) => {
    if (!target) return;
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    target.scrollIntoView({behavior: reducedMotion ? 'instant' : 'smooth', block:'start'});
    target.focus({preventScroll:true});
  };
  // The result is a new interface, not a chat message hidden far below the fold.
  // Focus and reveal it after React has committed the latest API response.
  useEffect(() => {
    if (!resultRevision) return;
    const frame = requestAnimationFrame(() => jumpTo(resultRef.current || workspaceRef.current));
    return () => cancelAnimationFrame(frame);
  }, [resultRevision]);
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data: result, error }) => { if (error) setNotice(error.message); setUser(result.session?.user || null); });
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => { setUser(session?.user || null); if (!session) { setConnected(false); setLive(false); setSaved([]); setShowSaved(false); } });
    return () => subscription.subscription.unsubscribe();
  }, []);
  useEffect(() => { const handler = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); commandRef.current?.focus(); } }; document.addEventListener('keydown', handler); return () => document.removeEventListener('keydown', handler); }, []);
  const reload = useCallback(async () => { const request = ++dataRequestRef.current; setLoading(true); setDataError(''); if (connected) setData({ clients: [], meetings: [], communications: [], usage: [], projects: [], tasks: [], issues: [] }); try { const result = await loadDataset(connected); if (request === dataRequestRef.current) setData(result); } catch (e) { if (request === dataRequestRef.current) setDataError(e instanceof Error ? e.message : 'Unable to load data.'); } finally { if (request === dataRequestRef.current) setLoading(false); } }, [connected]);
  useEffect(() => { void reload(); }, [reload]);
  async function submit(text: string, selection?: EnterpriseEntity) {
    if (!text.trim() || inFlight.current) return;
    inFlight.current = true;
    const request = ++requestRef.current;
    setInput(''); setNotice(''); setState('understanding');
    setCompanyGuide(null); setCompanyGuideAI(null); setCompanyGuideBusy(false); setCompanyGuideAIBusy(false); companyGuideQuestion.current = '';
    setWorkspaceAI(null); setWorkspaceAIBusy(false); setAIUsage(null);
    setGeneralAdviceQuestion(''); setGeneralAdviceAnswer(null); setGeneralAdviceBusy(false);
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    try {
      if (supabase && !selection && isGeneralAdviceQuestion(text)) {
        // General strategy is not a database fact or a fictional enterprise metric.
        // One bounded Groq request only for high-confidence generic queries.
        setEnterprise(null); setCompanyGuide(null); setPlan(initialPlan());
        enterpriseToken.current = null; previousEnterprisePrompt.current = '';
        setConnected(false); setLive(false);
        setGeneralAdviceQuestion(text); setGeneralAdviceBusy(true);
        setSource('KAI · general strategy AI');
        setState('success'); setResultRevision(revision => revision + 1);
        try {
          const answer = await fetchGeneralAdvice(text);
          if (request === requestRef.current) setGeneralAdviceAnswer(answer);
        } catch {
          if (request === requestRef.current) setGeneralAdviceAnswer({status:'fallback',advice:null});
        } finally {
          if (request === requestRef.current) setGeneralAdviceBusy(false);
        }
        return;
      }
      if (supabase && !selection && isCompanyKnowledgeQuestion(text)) {
        // Company knowledge is document-only: no DB snapshot, records or invented dashboard.
        setCompanyGuideBusy(true);
        setEnterprise(null); setPlan(initialPlan());
        setConnected(false); setLive(false);
        setSource('SORYU Knowledge Atlas · company guide');
        const guide = await fetchCompanyGuide(text);
        if (request !== requestRef.current) return;
        setCompanyGuide(guide); setCompanyGuideBusy(false);
        setState('success'); setResultRevision(revision => revision + 1);
        // Pass 12D.1: never spend Groq tokens simply by opening the company guide.
        // A visible button makes source-only versus Groq explanation a user choice.
        companyGuideQuestion.current = text;
        return;
      }
      if (supabase) {
        // Always use the authenticated enterprise v2 API. Never show fictional
        // demo-derived results after a failed enterprise request.
        const result = await planEnterprise(text, enterpriseToken.current, selection);
        if (request !== requestRef.current) return;
        const adapted = adaptEnterprisePlan(result);
        if (adapted) setPlan(adapted);
        else setPlan(initialPlan()); // Never retain the previous widgets after clarification or no matching records.
        setEnterprise(result);
        enterpriseToken.current = result.context_token || null;
        if (!selection) previousEnterprisePrompt.current = text;
        latestEnterpriseSelection.current = selection;
        setConnected(false); setLive(false);
        setSource(result.intelligence?.status === 'enriched' ? 'SORYU enterprise intelligence · Groq-ranked' : 'SORYU enterprise intelligence · deterministic');
        setState(result.intent.clarification ? 'clarification' : 'success');
        setResultRevision(revision => revision + 1);
        if (result.status === 'partial') setNotice('Partial result: check the evidence and limitations below.');
      } else {
        const localEdit = !/\bacme\b|\bnova\b|investigate|prepare|review projects/i.test(text) ? transform(text, plan) : null;
        const next = localEdit || planLocally(text, plan);
        if (request !== requestRef.current) return;
        setEnterprise(null); setPlan(next);
        setSource(localEdit ? 'Local context transformation' : 'Deterministic sample planner');
        setState(next.clarification ? 'clarification' : 'success');
        setResultRevision(revision => revision + 1);
      }
    } catch (e) {
      if (request === requestRef.current) {
        setCompanyGuideBusy(false);
        setState('error');
        setNotice(`${e instanceof Error ? e.message : 'Enterprise intelligence unavailable.'} Previous workspace preserved; no synthetic result was substituted.`);
      }
    } finally { inFlight.current = false; }
  }
  async function retryGeneralAdvice() {
    if (!generalAdviceQuestion || generalAdviceBusy) return;
    const request = requestRef.current;
    setGeneralAdviceBusy(true);
    setGeneralAdviceAnswer(null);
    try {
      const answer = await fetchGeneralAdvice(generalAdviceQuestion);
      if (request === requestRef.current) setGeneralAdviceAnswer(answer);
    } catch {
      if (request === requestRef.current) setGeneralAdviceAnswer({status:'fallback',advice:null});
    } finally {
      if (request === requestRef.current) setGeneralAdviceBusy(false);
    }
  }
  async function explainCompanyGuideOnDemand() {
    if (!companyGuide || companyGuide.status !== 'ready' || companyGuide.passages.length === 0 ||
        !companyGuideQuestion.current || companyGuideAIBusy) return;
    const request = requestRef.current;
    const question = companyGuideQuestion.current;
    setCompanyGuideAIBusy(true);
    setCompanyGuideAI(null);
    try {
      const result = await explainCompanyGuide(question);
      if (request === requestRef.current) setCompanyGuideAI(result);
    } catch {
      if (request === requestRef.current) setCompanyGuideAI({status: 'fallback', items: []});
    } finally {
      if (request === requestRef.current) setCompanyGuideAIBusy(false);
    }
  }
  async function explainCurrentWorkspace() {
    if (!enterprise || workspaceAIBusy || enterprise.intent.clarification) return;
    const request = requestRef.current;
    setWorkspaceAIBusy(true); setWorkspaceAI(null);
    try {
      const result = await explainWorkspace(previousEnterprisePrompt.current, latestEnterpriseSelection.current);
      if (request === requestRef.current) setWorkspaceAI(result);
    } catch {
      if (request === requestRef.current) setWorkspaceAI({status:'fallback', points:[], atlas_sources:[]});
    } finally { if (request === requestRef.current) setWorkspaceAIBusy(false); }
  }
  async function viewAIUsage() {
    try { setAIUsage(await fetchAIUsage()); }
    catch { setNotice('Process AI usage unavailable; check the Groq Console for official usage.'); }
  }
  function selectEnterprise(entity: EnterpriseEntity) {
    void submit(previousEnterprisePrompt.current, entity);
  }
  function reset() { requestRef.current++; inFlight.current = false; setCompanyGuide(null); setCompanyGuideAI(null); setCompanyGuideBusy(false); setCompanyGuideAIBusy(false); companyGuideQuestion.current = ''; setGeneralAdviceQuestion(''); setGeneralAdviceAnswer(null); setGeneralAdviceBusy(false); setWorkspaceAI(null); setWorkspaceAIBusy(false); setAIUsage(null); setEnterprise(null); enterpriseToken.current = null; previousEnterprisePrompt.current = ''; setPlan(initialPlan()); setState('idle'); setSource('Deterministic planner'); setNotice(''); }
  function toggleTask(id: string) { setCompleted(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  async function save() { if (enterprise) { setNotice('Saving a v2 enterprise workspace requires a v2 session contract; no incomplete snapshot was saved.'); return; } if (!user) { setAccountOpen(true); return; } setSaving(true); try { await saveWorkspace(plan); setNotice('Workspace saved to your Supabase account through FastAPI.'); } catch (e) { setNotice(e instanceof Error ? e.message : 'Save failed.'); } finally { setSaving(false); } }
  async function showHistory() { if (!user) { setAccountOpen(true); return; } try { setSaved(await savedWorkspaces()); setShowSaved(true); } catch (e) { setNotice(e instanceof Error ? e.message : 'Could not load saved workspaces.'); } }
  const scoped = enterprise ? enterpriseDataset(enterprise) : scopeData(data, plan);
  const enterpriseOnlyMessage = enterprise && enterprise.components.every(component => component.props.selector === 'insights');
  const functionalView = enterprise ? selectedFunctionalView(enterprise) : null;
  return <div className="app-shell kairos-sakura-theme">
    <aside className="sidebar"><SidebarSakuraBranches/><a className="brand" href="#main" onClick={e => { e.preventDefault(); reset(); }} aria-label="KAIROS home"><span className="brand-mark"><span/></span><span>カイロス <small>KAIROS</small></span></a><div className="workspace-label">YOUR SPACE <span>01</span></div><nav aria-label="Main navigation"><button className={plan.intent === 'overview' ? 'nav-item active' : 'nav-item'} onClick={reset}><LayoutDashboard size={18}/> Overview</button>{suggestions.map((s, i) => <button key={s.tag} className={`nav-item ${plan.intent === ['meeting', 'usage', 'projects'][i] ? 'active' : ''}`} disabled={busy} onClick={() => void submit(s.input)}><s.icon size={18}/>{['Meeting prep', 'Usage insights', 'Project review'][i]}</button>)}<div className="nav-divider"/><button className="nav-item" disabled={busy} onClick={() => void submit('I am a new employee. How do things work at SORYU SYSTEMS?')}><BookOpenText size={18}/> Company guide</button><button className="nav-item" disabled={busy} onClick={() => user ? setMeetingComposer(true) : setAccountOpen(true)}><CalendarDays size={18}/> Schedule a meeting</button><button className="nav-item" onClick={() => void showHistory()}><Save size={18}/> Saved workspaces</button></nav><div className="sidebar-bottom"><div className="kai-card"><Kai state={state} compact/><p>A workspace that<br/>thinks with you.</p><span>Less searching. More doing.</span></div><div className="event-label"><span className="red-dot"/> BUILT FOR HACKWAVE 3.0</div><button className="profile-button" onClick={() => setAccountOpen(!accountOpen)}><span className="avatar small"><UserRound size={16}/></span><span>{user?.email?.split('@')[0] || 'Employee'}<small>{user ? 'Connected account' : 'Employee access'}</small></span><ChevronDown size={14}/></button></div></aside>
    <div className="app-body"><header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{generalAdviceQuestion ? 'AI strategy guide' : enterprise ? enterprise.title : companyGuide || companyGuideBusy ? 'Company guide' : plan.intent === 'overview' ? 'Overview' : plan.intent === 'meeting' ? 'Meeting preparation' : plan.intent === 'usage' ? 'Usage investigation' : 'Project review'}</strong></div><div className="topbar-actions"><span className="mode-pill"><span/>{generalAdviceQuestion ? 'GENERAL AI' : enterprise || connected ? 'CONNECTED DATA' : 'LOCAL DATA'}</span><button className="icon-button" aria-label="Account settings" onClick={() => setAccountOpen(!accountOpen)}><UserRound size={18}/></button></div></header>
    <main id="main"><div className="page-heading"><div><div className="eyebrow"><span className="red-line"/> INTENT INTO ACTION</div><h1>{generalAdviceQuestion ? 'AI strategy guide' : enterprise ? enterprise.title : companyGuide || companyGuideBusy ? 'Company guide' : plan.intent === 'overview' ? <>Your focus.<br/><span>Your workspace.</span></> : plan.title}</h1><p>{generalAdviceQuestion ? 'General recommendations from KAI, separate from recorded enterprise facts.' : enterprise ? 'Your goal has been translated into an evidence-backed interface below.' : companyGuide || companyGuideBusy ? 'Retrieved from the SORYU Knowledge Atlas, with optional Groq explanation below.' : plan.intent === 'overview' ? 'The right interface at the right moment. Tell KAI what you want to accomplish.' : 'A workspace composed around your goal, with the context you need to act.'}</p></div><KairosHeroScene/></div>
    <section className="command-section" aria-label="Describe your goal"><div className="command-top"><span><Sparkles size={14}/> What are we working on?</span><span className="planner-label">{source}</span></div><form className="command-form" onSubmit={e => { e.preventDefault(); void submit(input); }}><Command size={22}/><label className="sr-only" htmlFor="intent">Describe your goal</label><input ref={commandRef} id="intent" maxLength={2000} value={input} onChange={e => setInput(e.target.value)} placeholder="Prepare for an OrbitPay client meeting…" disabled={busy}/><kbd>Ctrl K</kbd><button className="primary" disabled={busy || !input.trim()} aria-label="Compose workspace">{busy ? 'Composing…' : <><span>Compose</span><ArrowRight size={17}/></>}</button></form><div className="command-bottom"><Kai state={state}/><span>Safe components. Relevant context. Your control.</span></div></section>
    {notice && <div className="notice" role="status"><span>{notice}</span><button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><X size={16}/></button></div>}
    {plan.clarification && <section className="clarification" role="region" aria-label="Clarification required"><HelpCircle size={22}/><div><h2>{plan.clarification.question}</h2><p>Your current workspace is kept until you choose.</p><div className="chips">{plan.clarification.options.map(option => <button key={option} disabled={busy} onClick={() => void submit(option)}>{option}<ArrowRight size={14}/></button>)}</div></div></section>}
    {generalAdviceQuestion && <div ref={resultRef} className="composed-result-anchor" tabIndex={-1}>
      <GeneralAdvice question={generalAdviceQuestion} result={generalAdviceAnswer} pending={generalAdviceBusy} onRetry={() => void retryGeneralAdvice()}/>
    </div>}
    {companyGuideBusy && <div ref={resultRef} className="composed-result-anchor" tabIndex={-1} role="status">Loading company reference material…</div>}
    {companyGuide && <div ref={resultRef} className="composed-result-anchor" tabIndex={-1}><CompanyGuide guide={companyGuide} ai={companyGuideAI} aiPending={companyGuideAIBusy} onExplain={() => void explainCompanyGuideOnDemand()}/></div>}
    {enterprise && <div ref={resultRef} id="kairos-composed-result" className="composed-result-anchor" tabIndex={-1}>
      <IntentResultStage result={enterprise} functionalView={functionalView} visibleWidgetTitles={plan.layout.map(widget => widget.title)} onWorkspace={() => jumpTo(workspaceRef.current)} onEvidence={() => jumpTo(evidenceRef.current)}/>
    </div>}
    {enterprise && !enterprise.intent.clarification && <AiExplainPanel ai={workspaceAI} busy={workspaceAIBusy}
      onExplain={() => void explainCurrentWorkspace()} usage={aiUsage} onUsage={() => void viewAIUsage()}/>}
    {enterprise?.intent.clarification && <div ref={evidenceRef} className="intent-evidence-anchor" tabIndex={-1}><EnterpriseAnswerView result={enterprise} onSelect={selectEnterprise}/></div>}
    {plan.intent === 'overview' && !enterprise && !companyGuide && !companyGuideBusy && !generalAdviceQuestion && <section className="suggestion-grid" aria-label="Suggested goals">{suggestions.map((s, i) => <button className="suggestion" key={s.tag} onClick={() => void submit(s.input)} disabled={busy}><div className="row between"><span className={`suggestion-icon tone-${i}`}><s.icon size={21}/></span><ArrowUpRight size={17}/></div><span className="eyebrow">{s.tag}</span><h2>{s.label}</h2><p>{s.detail}</p></button>)}</section>}
    {!companyGuide && !companyGuideBusy && !generalAdviceQuestion && <div className="workspace-toolbar"><div><h2>{plan.intent === 'overview' && !enterprise ? 'Your workspace, at a glance' : 'Your adaptive workspace'} <span className="count">{enterprise ? Math.max(plan.layout.length, functionalView ? 1 : 0) : plan.layout.length}</span></h2><p>{enterprise ? 'Authorized SORYU records' : plan.selectedEntityIds.length ? scoped.clients.map(c => c.name).join(' · ') : 'All clients'} <span>·</span> {enterprise ? 'Live database response' : `As of ${DEMO_DATE}`} </p></div><div className="toolbar-buttons"><button className="secondary" onClick={() => setExplain(!explain)} aria-expanded={explain}><Sparkles size={14}/> Why this workspace?</button><button className="icon-button" onClick={() => void save()} disabled={saving || busy} aria-label="Save workspace to account"><Save size={17}/></button></div></div>}
    {!companyGuide && !companyGuideBusy && !generalAdviceQuestion && plan.intent !== 'overview' && <div className="filter-bar"><label>Date window<select aria-label="Date window" value={plan.filters.days} disabled={busy} onChange={e => void submit(`Show only the last ${e.target.value} days`)}>{[7, 14, 30].map(d => <option key={d} value={d}>Last {d} days</option>)}</select></label><button className={plan.filters.unresolvedOnly ? 'chip selected' : 'chip'} onClick={() => void submit(plan.filters.unresolvedOnly ? 'Reset filters' : 'Focus on unresolved issues')} disabled={busy}>Unresolved issues {plan.filters.unresolvedOnly && <Check size={13}/>}</button>{plan.layout.some(w => w.selector === 'usage') && <><button className={plan.filters.compare ? 'chip selected' : 'chip'} onClick={() => void submit('Compare this with the previous period')} disabled={busy || plan.filters.compare}><ArrowDownUp size={13}/> Compare periods</button><button className="chip" onClick={() => void submit('Show this information as a table instead')} disabled={busy}>Show as table</button></>}<button className="text-button" onClick={() => void submit('Reset filters')} disabled={busy}><RotateCcw size={13}/> Reset filters</button><span className="filter-help">Dates filter history; upcoming meetings and open tasks stay visible.</span></div>}
    {!companyGuide && !companyGuideBusy && !generalAdviceQuestion && <div ref={workspaceRef} id="kairos-adaptive-workspace" tabIndex={-1} className={`workspace-content ${explain ? 'with-explanation' : ''}`}>{functionalView ? <FunctionalWorkspace result={enterprise!} onIntent={text => void submit(text)}/> : enterpriseOnlyMessage ? <div className="empty" role="status">No widget layout was returned. See the clarification and evidence above.</div> : <Workspace plan={plan} data={scoped} completed={completed} onToggleTask={toggleTask} onIntent={text => void submit(text)} loading={enterprise ? false : loading} error={enterprise ? '' : dataError} onRetry={() => void reload()}/>}{explain && <aside className="explanation"><div className="row between"><span className="explain-icon"><Sparkles size={18}/></span><span className="eyebrow">THE REASONING</span></div><h2>Why this workspace?</h2><p className="explain-intro">Every component has a purpose.</p><ol>{plan.explanations.map((reason, i) => <li key={`${i}-${reason}`}>{reason}</li>)}</ol><div className="explain-divider"/>{[...plan.layout].sort((a, b) => a.order - b.order).map(w => <details key={w.id}><summary>{w.title}<ChevronDown size={13}/></summary><p>{w.reason}</p><span className="source">Source: {w.selector} · {w.selector === 'insights' || w.selector === 'activity' ? 'derived from scoped records' : `${scoped[w.selector as keyof typeof scoped]?.length ?? 0} scoped records`}</span></details>)}<div className="explain-footer"><span className="green-dot"/>{source}<small>{enterprise ? 'Evidence from authenticated SORYU API' : connected ? 'Supabase records' : 'Local sample records · no cloud calls'}</small></div></aside>}</div>}
    {enterprise && !enterprise.intent.clarification && <div ref={evidenceRef} id="kairos-source-records" className="intent-evidence-anchor" tabIndex={-1}><EnterpriseAnswerView result={enterprise} onSelect={selectEnterprise}/></div>}
    {!companyGuide && !companyGuideBusy && !generalAdviceQuestion && <section className="connection-settings" aria-label="Connection settings"><div><Database size={16}/><strong>Data & intelligence</strong><span>{enterprise ? 'Verified enterprise response' : connected ? 'Supabase records' : 'Local sample records'}</span></div><label><input type="checkbox" checked={Boolean(enterprise) || connected} disabled={Boolean(enterprise) || !user || !supabase || busy} onChange={e => { setConnected(e.target.checked); setLive(false); }}/> Connected data</label><label><input type="checkbox" checked={live} disabled={Boolean(enterprise) || !connected || !user || busy} onChange={e => setLive(e.target.checked)}/> Enable Live AI</label><p>{!user ? 'Sign in to enable Supabase. ' : ''}{enterprise?.intelligence?.status === 'enriched' ? 'Enterprise v2 is Groq-ranked with verified records; no AI-generated records or claims.' : 'Enterprise v2 uses deterministic, evidence-backed planning without Groq calls by default. Groq explanations are available on demand.'} Legacy mode is retained for comparison.</p></section>}
    <footer><span><span className="brand-dot"/> KAIROS <small>カイロス</small></span><p>Made for the moment. Built for HackWave 3.0.</p><span>Product experience · curated sample data</span></footer>
    </main>{meetingComposer && user && <MeetingScheduler onClose={() => setMeetingComposer(false)} onCreated={day => { setMeetingComposer(false); const from = day; const end = new Date(`${day}T12:00:00Z`); end.setUTCDate(end.getUTCDate()+6); void submit(`Show my schedule from ${from} to ${end.toISOString().slice(0,10)}`); }}/>} {accountOpen && <Account user={user} onClose={() => setAccountOpen(false)}/>} {showSaved && <section className="saved-panel"><div className="row between"><h2>Saved workspaces</h2><button className="icon-button" aria-label="Close saved workspaces" onClick={() => setShowSaved(false)}><X size={18}/></button></div>{!saved.length ? <p>No saved workspaces yet. Use the save button above your workspace.</p> : saved.map(row => <button key={row.id} className="saved-item" disabled={busy} onClick={() => { setPlan(row.plan); setShowSaved(false); setSource('Restored saved plan'); setState(row.plan.clarification ? 'clarification' : 'success'); }}>{row.title}<small>{new Date(row.created_at).toLocaleString()}</small><ArrowRight size={16}/></button>)}</section>}</div>
  </div>;
}
