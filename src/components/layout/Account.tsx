import { useEffect, useState } from 'react';
import { LogOut, X } from 'lucide-react';
import type { User } from '@supabase/supabase-js';
import { supabase } from '../../lib/supabase';
export function Account({ user, onClose }: { user: User | null; onClose: () => void }) {
    const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, [onClose]);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (!supabase) return; setBusy(true); setMessage('');
    try { const result = await supabase.auth.signInWithPassword({ email, password }); if (result.error) throw result.error; onClose(); } catch (e) { setMessage(e instanceof Error ? e.message : 'Unable to sign in.'); } finally { setBusy(false); }
  }
  return <div className="account-panel"><div className="row between"><h2>{user ? 'Your account' : 'Employee sign in'}</h2><button className="icon-button" onClick={onClose} aria-label="Close account panel"><X size={18}/></button></div>{!supabase ? <p>Demo mode works without an account. Add the Supabase URL and publishable key to enable authentication and saved workspaces.</p> : user ? <><p>{user.email}</p><button className="secondary" onClick={async () => { const { error } = await supabase!.auth.signOut(); if (error) setMessage(error.message); else onClose(); }}><LogOut size={15}/> Sign out</button></> : <form onSubmit={submit}><label>Email<input type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)}/></label><label>Password<input type="password" required minLength={8} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)}/></label><button className="primary" disabled={busy}>{busy ? 'Please wait…' : 'Sign in'}</button></form>}{message && <p role="status" className="notice">{message}</p>}</div>;
}
