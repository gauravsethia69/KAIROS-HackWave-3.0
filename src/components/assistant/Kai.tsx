export type KaiState = 'idle' | 'understanding' | 'composing' | 'clarification' | 'success' | 'error';
const labels: Record<KaiState, string> = { idle: 'Ready when you are', understanding: 'Understanding your intent', composing: 'Composing your workspace', clarification: 'A little more context?', success: 'Your workspace is ready', error: 'Offline planner is ready' };
export function Kai({ state, compact = false }: { state: KaiState; compact?: boolean }) {
  return <div className={`kai ${state} ${compact ? 'compact' : ''}`}>
    <svg width="64" height="60" viewBox="0 0 80 72" role="img" aria-label={`KAI: ${labels[state]}`}>
      <path d="M16 28 12 8 31 19M49 19 68 8 64 30" fill="#b9c3cf" stroke="#f6f0e6" strokeWidth="2" />
      <path d="m17 14 3 10 7-3m36-7-3 10-7-3" fill="#d9364f" />
      <rect x="10" y="20" width="60" height="44" rx="20" fill="#c9d2da" />
      <rect x="17" y="27" width="46" height="28" rx="12" fill="#121820" />
      {state === 'success' ? <path d="m26 41 4-4 4 4m12 0 4-4 4 4" fill="none" stroke="#73d9ed" strokeWidth="3" strokeLinecap="round" /> : state === 'error' ? <path d="m26 39 8 4m12 0 8-4" stroke="#f5a9bf" strokeWidth="3" /> : <g fill="#73d9ed"><rect x="26" y="36" width="7" height={state === 'idle' ? '7' : '10'} rx="3"/><rect x="47" y="36" width="7" height={state === 'clarification' ? '5' : '7'} rx="3"/></g>}
      <path d="m37 47 3 2 3-2" fill="none" stroke="#73d9ed" strokeWidth="1.5" />
      <circle cx="40" cy="60" r="2" fill="#d9364f"/><path d="M9 37H5m66 0h4" stroke="#f5a9bf" strokeWidth="3" strokeLinecap="round"/>
    </svg>
    {!compact && <div><span className="eyebrow">KAI ASSISTANT</span><p role="status">{labels[state]}</p></div>}
  </div>;
}
