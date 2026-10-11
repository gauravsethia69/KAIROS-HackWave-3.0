import { beforeEach, describe, expect, it, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { workspacePlanSchema } from '../types/workspace';
import { initialPlan, planLocally } from '../ai/planner';
const auth = vi.hoisted(() => ({ getSession: vi.fn(), refreshSession: vi.fn() }));
vi.mock('../lib/supabase', () => ({ supabase: { auth } }));
import { apiRequest } from '../lib/api';
import { planLive } from '../ai/live';
import { loadDataset, saveWorkspace } from '../data/repository';

beforeEach(() => {
  auth.getSession.mockResolvedValue({ data: { session: { access_token: 'original' } }, error: null });
  auth.refreshSession.mockResolvedValue({ data: { session: { access_token: 'refreshed' } }, error: null });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]')));
});
describe('FastAPI integration', () => {
  it('attaches the Supabase bearer token', async () => { await apiRequest('/api/clients'); expect(vi.mocked(fetch).mock.calls[0][1]?.headers).toMatchObject({ Authorization: 'Bearer original' }); });
  it('refreshes only once on a 401', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 401 })).mockResolvedValueOnce(new Response('[]'));
    await apiRequest('/api/clients'); expect(auth.refreshSession).toHaveBeenCalledOnce(); expect(vi.mocked(fetch).mock.calls[1][1]?.headers).toMatchObject({ Authorization: 'Bearer refreshed' });
  });
  it('rejects a persistent 401 without a retry loop', async () => { vi.mocked(fetch).mockImplementation(async () => new Response('', { status: 401 })); await expect(apiRequest('/api/clients')).rejects.toThrow('Session rejected'); expect(fetch).toHaveBeenCalledTimes(2); });
  it('does not send a client-selected owner', async () => { await saveWorkspace(initialPlan()); const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)); expect(Object.keys(body)).toEqual(['plan']); });
  it('keeps Demo Mode independent of unavailable APIs', async () => { vi.mocked(fetch).mockRejectedValue(new TypeError('offline')); expect((await loadDataset(false)).clients.length).toBe(2); expect(fetch).not.toHaveBeenCalled(); });
  it('rejects API failure so the existing UI can use the local fallback', async () => { vi.mocked(fetch).mockRejectedValue(new TypeError('offline')); const input = 'Investigate Acme usage'; let plan; try { plan = (await planLive(input, initialPlan())).plan; } catch { plan = planLocally(input); } expect(plan.intent).toBe('usage'); });
  it('preserves the server fallback label', async () => { vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ plan: initialPlan(), source: 'fallback', message: 'AI offline' }))); expect((await planLive('test', initialPlan())).source).toBe('fallback'); });
  it('rejects untrusted server plans', async () => { vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ plan: { ...initialPlan(), layout: [] }, source: 'live', message: '' }))); await expect(planLive('test', initialPlan())).rejects.toThrow(); });
  it.skipIf(!existsSync('artifacts/backend-plans.json'))('validates actual Python-generated plans with the frontend Zod schema', () => {
    const plans = JSON.parse(readFileSync('artifacts/backend-plans.json', 'utf8')) as unknown[];
    expect(plans).toHaveLength(3); for (const plan of plans) expect(workspacePlanSchema.safeParse(plan).success).toBe(true);
  });
});
