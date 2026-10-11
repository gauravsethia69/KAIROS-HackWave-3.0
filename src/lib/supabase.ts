import { createClient } from '@supabase/supabase-js';
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
function configure() {
  if (!url || !key) return null;
  try { const parsed = new URL(url); if (!['https:', 'http:'].includes(parsed.protocol)) return null; return createClient(url, key); } catch { return null; }
}
export const supabase = configure();
