// Isolated browser checks: auth and /api are mocked; no live credentials/services.
// Run against Vite with the existing PLAYWRIGHT_MODULE / PLAYWRIGHT_CHANNEL setup.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { build } from 'esbuild';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.KAIROS_URL || 'http://127.0.0.1:5179';
const mock = `
const listeners = new Set();
let session = sessionStorage.getItem('gate-test-session') ? {access_token:'test-only',user:{id:'test-user',email:'fixture@example.test'}} : null;
const emit = () => listeners.forEach(fn=>fn(session?'SIGNED_IN':'SIGNED_OUT',session));
export const supabase = {auth:{
getSession:async()=>({data:{session}}),
refreshSession:async()=>({data:{session}}),
onAuthStateChange:fn=>{listeners.add(fn); return {data:{subscription:{unsubscribe:()=>listeners.delete(fn)}}}},
signInWithPassword:async({password})=>{
 if(password==='incorrect') return {error:new Error('Invalid login credentials')};
 session={access_token:'test-only',user:{id:'test-user',email:'fixture@example.test'}};
 sessionStorage.setItem('gate-test-session','yes'); emit(); emit(); return {error:null};
},
signOut:async()=>{session=null;sessionStorage.removeItem('gate-test-session');emit();return {error:null}}
}};
window.gateTestAuth = supabase.auth;
window.gateTestRepeat = emit;
`;
// Bundle a mocked copy, not production output; avoid the stalled Vite dev server.
let server;
if (!process.env.KAIROS_URL) {
  await build({entryPoints:['src/main.tsx'], bundle:true, outdir:'artifacts/gate-test', format:'esm', jsx:'automatic', external:['/images/*'],
    define:{'import.meta.env':'{}'}, plugins:[{name:'gate-test-mocks',setup(b){
      b.onLoad({filter:/[\\/]lib[\\/]supabase\.ts$/},()=>({contents:mock,loader:'js'}));
      b.onLoad({filter:/[\\/]styles\.css$/},args=>({contents:readFileSync(args.path,'utf8').replace('@import "tailwindcss";','').replace(/@theme\s*\{[^}]*\}/,''),loader:'css'}));
    }}]});
  server = createServer((req,res)=>{
    const path = new URL(req.url,base).pathname;
    const files={'/main.js':['artifacts/gate-test/main.js','text/javascript'],'/main.css':['artifacts/gate-test/main.css','text/css'],
      '/images/kairos-gate-login.png':['public/images/kairos-gate-login.png','image/png'], '/images/kairos-japan-hero.webp':['public/images/kairos-japan-hero.webp','image/webp']};
    if(path==='/'){res.setHeader('Content-Type','text/html');res.end('<div id="root"></div><link rel="stylesheet" href="/main.css"><script type="module" src="/main.js"></script>');return;}
    if(files[path]){res.setHeader('Content-Type',files[path][1]);res.end(readFileSync(files[path][0]));return;}
    res.writeHead(404);res.end();
  });
  await new Promise(resolve=>server.listen(5179,'127.0.0.1',resolve));
}
const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' });
let passed = 0;
async function check(name, run, options = {}) {
  console.log(`Checking: ${name}`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...options });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let status = 200;
  let authorize;
  let pending = false;
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/src/lib/supabase.ts') return route.fulfill({ contentType: 'application/javascript', body: mock });
    if (url.pathname === '/api/auth/me') {
      if (pending) await new Promise(resolve => { authorize = resolve; });
      return route.fulfill({ status, json: status === 200 ? {user_id:'test-user',employee_id:'e-test',access_role:'employee'} : {detail:'mock failure'} });
    }
    if (url.pathname.startsWith('/api/')) return route.fulfill({status:503,json:{detail:'mock unavailable'}});
    if (url.origin !== new URL(base).origin) return route.abort();
    return route.continue();
  });
  await page.addInitScript(() => {
    window.gateCount = 0;
    new MutationObserver(records => {
      for (const record of records) for (const node of record.addedNodes) {
        if (node instanceof Element) window.gateCount += Number(node.matches('.kairos-gate-opening')) + node.querySelectorAll('.kairos-gate-opening').length;
      }
    }).observe(document, {childList:true,subtree:true});
  });
  const login = async (password = 'fixture-password') => {
    await page.getByRole('button', {name:'Employee sign in', exact:true}).first().click();
    await page.locator('#employee-email').fill('fixture@example.test');
    await page.locator('#employee-password').fill(password);
    await page.getByRole('button', {name:'Sign in to KAIROS'}).click();
  };
  try {
    await page.goto(base, {waitUntil:'domcontentloaded'});
    await run({ page, login, setStatus: value => {status=value;}, hold:()=>{pending=true;}, release:async()=>{
      for (let i=0; !authorize && i<100; i++) await new Promise(resolve=>setTimeout(resolve,20));
      assert.ok(authorize, 'Authorization request must be pending');
      const resolve = authorize; authorize = undefined; resolve();
    } });
    assert.deepEqual(errors, [], 'No uncaught browser errors');
    console.log(`PASS ${++passed}: ${name}`);
  } catch (error) {
    console.error('Browser check failed:', error.message, 'Page errors:', errors);
    throw error;
  } finally { authorize?.(); await context.close(); }
}
const workspace = page => page.getByRole('textbox', {name:'Describe your goal'}).waitFor();
const ended = page => page.locator('.kairos-gate-opening').waitFor({state:'detached'});
try {
  await check('authorized interactive login; pending gate; repeat events; logout/login', async ({page,login,hold,release}) => {
    hold(); await login();
    await page.getByText('Verifying your employee access…').waitFor();
    assert.equal(await page.locator('.kairos-gate-opening').count(),0);
    assert.equal(await page.getByRole('textbox',{name:'Describe your goal'}).count(),0);
    await release(); await page.locator('.kairos-gate-opening').waitFor();
    assert.equal(await page.locator('[inert]').count(),1);
    mkdirSync('artifacts',{recursive:true});
    await page.screenshot({path:'artifacts/gate-desktop.png'});
    await page.evaluate(()=>window.gateTestRepeat());
    await ended(page); await workspace(page);
    assert.equal(await page.evaluate(()=>window.gateCount),1);
    assert.equal(await page.locator('[inert]').count(),0);
    await page.evaluate(()=>window.gateTestAuth.signOut());
    await login();
    await page.getByText('Verifying your employee access…').waitFor(); await release();
    await page.locator('.kairos-gate-opening').waitFor(); await ended(page);
    assert.equal(await page.evaluate(()=>window.gateCount),2);
  });
  await check('wrong password does not animate', async ({page,login}) => {
    await login('incorrect'); await page.getByText('Invalid login credentials').waitFor();
    assert.equal(await page.evaluate(()=>window.gateCount),0);
  });
  for (const [name,status] of [['unlinked',403],['disabled',403],['rejected token',401],['backend unavailable',503]]) {
    await check(`${name} does not animate or mount workspace`, async ({page,login,setStatus}) => {
      setStatus(status); await login(); await page.locator('.landing-auth-loading[role=alert]').waitFor();
      assert.equal(await page.evaluate(()=>window.gateCount),0);
      assert.equal(await page.getByRole('textbox',{name:'Describe your goal'}).count(),0);
    });
  }
  await check('refresh restores session without replay', async ({page,login}) => {
    await login(); await workspace(page); await ended(page); await page.reload(); await workspace(page);
    assert.equal(await page.evaluate(()=>window.gateCount),0);
  });
  await check('mobile artwork fits; workspace remains interactive', async ({page,login}) => {
    await login(); await page.locator('.kairos-gate-opening').waitFor();
    await page.screenshot({path:'artifacts/gate-mobile.png'});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await ended(page); await workspace(page);
    await page.getByRole('textbox',{name:'Describe your goal'}).fill('Review projects');
  }, {viewport:{width:390,height:844}});
  await check('reduced motion skips visible animation', async ({page,login}) => {
    await login(); await workspace(page); await ended(page);
    assert.equal(await page.locator('[inert]').count(),0);
  }, {reducedMotion:'reduce'});
  await check('missing image safely opens workspace', async ({page,login}) => {
    await page.route('**/images/kairos-gate-login.png',route=>route.abort());
    await login(); await workspace(page); await ended(page);
    assert.equal(await page.locator('[inert]').count(),0);
  });
} finally { await browser.close(); if(server) await new Promise(resolve=>server.close(resolve)); }
console.log(`${passed} mocked browser checks passed; no live authentication performed.`);
