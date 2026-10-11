import { beforeEach, describe, expect, it, vi } from 'vitest';
import { initialPlan } from '../ai/planner';

const mocks = vi.hoisted(() => ({ getUser: vi.fn(), rpc: vi.fn() }));
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ auth: { getUser: mocks.getUser }, rpc: mocks.rpc }) }));
let handler: (request: Request) => Promise<Response>;
const env: Record<string, string> = {};
vi.stubGlobal('Deno', { env: { get: (key: string) => env[key] }, serve: (fn: typeof handler) => { handler = fn; } });
// The runtime handler is exercised under mocked Deno/auth/fetch. This is not an Edge deployment test.
const path = '../../supabase/functions/plan-workspace/index.ts';
await import(path);
const request = (body: unknown = { input: 'Prepare for Acme meeting', previous: initialPlan() }, token = 'test-token') => new Request('https://example.test/plan-workspace', { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify(body) });
beforeEach(() => {
  for (const key of Object.keys(env)) delete env[key];
  Object.assign(env, { SUPABASE_URL: 'https://example.test', SUPABASE_ANON_KEY: 'public-test', AI_API_KEY: 'server-secret-test', AI_BASE_URL: 'https://provider.example/v1', AI_MODEL: 'configured-test-model' });
  mocks.getUser.mockResolvedValue({ data: { user: { id: 'user-one' } }, error: null }); mocks.rpc.mockResolvedValue({ data: true, error: null });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(initialPlan()) } }] }), { status: 200 })));
});
describe('Edge request boundary with mocked infrastructure', () => {
  it('rejects missing authentication before provider access', async () => { expect((await handler(request(undefined, ''))).status).toBe(401); expect(fetch).not.toHaveBeenCalled(); });
  it('rejects invalid tokens', async () => { mocks.getUser.mockResolvedValue({ data: { user: null }, error: new Error('Invalid') }); expect((await handler(request())).status).toBe(401); expect(fetch).not.toHaveBeenCalled(); });
  it('rejects oversized prompts', async () => { expect((await handler(request({ input: 'a'.repeat(2001), previous: initialPlan() }))).status).toBe(400); expect(fetch).not.toHaveBeenCalled(); });
  it('rejects oversized request bodies', async () => { expect((await handler(request({ input: 'a'.repeat(25000), previous: initialPlan() }))).status).toBe(400); });
  it('returns unavailable when AI is unconfigured', async () => { delete env.AI_API_KEY; expect((await handler(request())).status).toBe(503); expect(fetch).not.toHaveBeenCalled(); });
  it('enforces the rate-limit result', async () => { mocks.rpc.mockResolvedValue({ data: false, error: null }); expect((await handler(request())).status).toBe(429); expect(fetch).not.toHaveBeenCalled(); });
  it('fails closed if the rate limiter fails', async () => { mocks.rpc.mockResolvedValue({ data: null, error: new Error('Offline') }); expect((await handler(request())).status).toBe(503); expect(fetch).not.toHaveBeenCalled(); });
  it('returns a validated plan without server credentials', async () => { const result = await handler(request()); expect(result.status).toBe(200); const text = await result.text(); expect(JSON.parse(text)).toEqual(initialPlan()); expect(text).not.toContain('server-secret-test'); expect(fetch).toHaveBeenCalledTimes(1); });
  it('rejects invalid model-selected components', async () => { const plan = initialPlan(); (plan.layout[0] as { type: string }).type = 'ExecuteSQL'; vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify(plan) } }] }))); expect((await handler(request())).status).toBe(502); });
  it('returns safe failures for provider errors and timeouts', async () => { vi.mocked(fetch).mockRejectedValue(new Error('secret upstream detail')); const result = await handler(request()); expect(result.status).toBe(502); expect(await result.text()).not.toContain('secret upstream'); });
  it('rejects an insecure endpoint', async () => { env.AI_BASE_URL = 'http://provider.example'; expect((await handler(request())).status).toBe(503); expect(fetch).not.toHaveBeenCalled(); });
  it('handles preflight without authentication', async () => { expect((await handler(new Request('https://example.test', { method: 'OPTIONS' }))).status).toBe(200); expect(fetch).not.toHaveBeenCalled(); });
});
