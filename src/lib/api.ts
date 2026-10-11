import { supabase } from './supabase';

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!supabase) throw new Error('Supabase authentication is not configured.');
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error('Sign in to use the connected backend.');
  const send = (token: string) => fetch(`${base}${path}`, { ...init, headers: { ...init.headers, 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(25000) });
  let response = await send(data.session.access_token);
  if (response.status === 401) {
    // Refresh once through Supabase; never retry a business operation indefinitely.
    const refreshed = await supabase.auth.refreshSession();
    if (refreshed.error || !refreshed.data.session) throw new Error('Session expired. Please sign in again.');
    response = await send(refreshed.data.session.access_token);
    if (response.status === 401) throw new Error('Session rejected. Please sign in again.');
  }
  if (!response.ok) throw new Error(`Backend request failed (${response.status}). Check the connection or use Demo Mode.`);
  return response.json() as Promise<T>;
}
