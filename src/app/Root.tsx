import { lazy, Suspense, useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { Landing } from '../components/landing/Landing';
import { apiRequest } from '../lib/api';
import { supabase } from '../lib/supabase';
import { GateOpening } from '../components/transitions/GateOpening';
import { gateLogin } from '../components/transitions/gateLogin';

const App = lazy(() => import('./App'));

type AccessState = {
  token: string;
  kind: 'allowed' | 'denied' | 'unavailable';
};

function Loading({ message }: { message: string }) {
  return <div className="landing-auth-loading" role="status" aria-live="polite">
    <span>カイロス</span><p>{message}</p>
  </div>;
}

export default function Root() {
  const [checking, setChecking] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [pendingGoal, setPendingGoal] = useState('');
  const [access, setAccess] = useState<AccessState | null>(null);
  const [retry, setRetry] = useState(0);
  const [openingGate, setOpeningGate] = useState(false);

  useEffect(() => {
    const image = new Image();
    image.src = '/images/kairos-gate-login.png';
  }, []);

  useEffect(() => {
    if (!supabase) { setChecking(false); return; }
    let alive = true;
    supabase.auth.getSession().then(({ data, error }) => {
      if (!alive) return;
      setSession(error ? null : data.session);
      setChecking(false);
    }).catch(() => { if (alive) { setSession(null); setChecking(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, currentSession) => {
      if (!alive) return;
      if (!currentSession) { gateLogin.reset(); setOpeningGate(false); setAccess(null); }
      setSession(currentSession);
      setChecking(false);
    });
    return () => { alive = false; listener.subscription.unsubscribe(); };
  }, []);

  // A valid Supabase session is NOT sufficient: the backend must confirm that
  // this exact verified Auth UUID is linked to an enabled SORYU employee.
  useEffect(() => {
    if (!session?.access_token) return;
    let alive = true;
    const token = session.access_token;
    apiRequest<{ user_id: string; employee_id: string; access_role: string }>('/api/auth/me')
      .then(() => {
        if (!alive) return;
        if (gateLogin.consume()) setOpeningGate(true);
        setAccess({ token, kind: 'allowed' });
      })
      .catch((error: unknown) => {
        if (!alive) return;
        gateLogin.reset();
        setOpeningGate(false);
        const denied = error instanceof Error && error.message.includes('(403)');
        setAccess({ token, kind: denied ? 'denied' : 'unavailable' });
      });
    return () => { alive = false; };
  }, [session?.access_token, retry]);

  if (checking) return <Loading message="Preparing your workspace…"/>;
  if (!session) return <Landing configured={Boolean(supabase)} pendingGoal={pendingGoal} onGoalChange={setPendingGoal}/>;

  const status = access?.token === session.access_token ? access.kind : null;
  if (status === null) return <Loading message="Verifying your employee access…"/>;
  if (status !== 'allowed') return <div className="landing-auth-loading" role="alert">
    <span>カイロス</span>
    <p>{status === 'denied'
      ? 'This account is not linked to an enabled SORYU employee.'
      : 'Unable to verify employee access. Please check the backend connection.'}</p>
    <div style={{ display: 'flex', gap: 12 }}>
      <button type="button" onClick={() => { setAccess(null); setRetry(value => value + 1); }}>Try again</button>
      <button type="button" onClick={() => { void supabase?.auth.signOut(); }}>Sign out</button>
    </div>
  </div>;

  return <Suspense fallback={<Loading message="Opening your workspace…"/>}>
    <div inert={openingGate || undefined} style={{ display: 'contents' }}>
      <App initialPrompt={pendingGoal}/>
    </div>
    {openingGate && <GateOpening onComplete={() => setOpeningGate(false)}/>}
  </Suspense>;
}
