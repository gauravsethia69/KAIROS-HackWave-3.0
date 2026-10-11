import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Eye, EyeOff, LockKeyhole, X } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { gateLogin } from '../transitions/gateLogin';

export function EmployeeLogin({ configured, onClose }: { configured: boolean; onClose: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const emailInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    emailInput.current?.focus();
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [onClose]);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || busy) return;
    setBusy(true);
    setError('');
    gateLogin.begin();
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (authError) throw authError;
      // Auth-state listener in the root component will reveal the workspace.
      onClose();
    } catch (e) {
      gateLogin.reset();
      setError(e instanceof Error ? e.message : 'Sign in failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return <div className="landing-login-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <section className="landing-login-dialog" role="dialog" aria-modal="true" aria-labelledby="employee-login-heading" aria-describedby="employee-login-description">
      <button className="landing-login-close" type="button" aria-label="Close sign in" onClick={onClose}><X size={18}/></button>
      <div className="landing-login-mark"><LockKeyhole size={22}/></div>
      <p className="landing-login-overline">SORYU SYSTEMS · EMPLOYEE ACCESS</p>
      <h2 id="employee-login-heading">Welcome back.</h2>
      <p id="employee-login-description">Sign in with your company credentials to continue to KAIROS.</p>
      {!configured ? <div className="landing-login-warning" role="alert">Supabase authentication is not configured. Add the project URL and publishable key to your frontend environment and restart Vite.</div> : <form onSubmit={signIn}>
        <label htmlFor="employee-email">Work email</label>
        <input ref={emailInput} id="employee-email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@company.com"/>
        <label htmlFor="employee-password">Password</label>
        <div className="landing-password-wrap">
          <input id="employee-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/>
          <button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?'Hide password':'Show password'}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button>
        </div>
        {error && <div className="landing-login-error" role="alert">{error}</div>}
        <button className="landing-login-submit" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to KAIROS'}<ArrowRight size={18}/></button>
      </form>}
      <div className="landing-login-foot"><LockKeyhole size={13}/> Authorized employees only</div>
    </section>
  </div>;
}
