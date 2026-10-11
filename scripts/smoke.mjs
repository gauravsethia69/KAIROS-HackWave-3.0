// Run against `npm run dev` with Playwright available. PLAYWRIGHT_MODULE can point
// to an existing Playwright installation; no browser package is needed at runtime.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) });
const page = await browser.newPage({ viewport: { width: 1440, height: 1080 }, reducedMotion: 'reduce' });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
mkdirSync('artifacts', { recursive: true });
async function command(text) {
  const field = page.getByRole('textbox', { name: 'Describe your goal' });
  await field.fill(text);
  await page.getByRole('button', { name: 'Compose workspace', exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('.kai.understanding, .kai.composing'));
}
async function noOverflow() {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Page should not overflow horizontally');
}
try {
  await page.goto(process.env.KAIROS_URL || 'http://127.0.0.1:5173');
  await page.getByRole('heading', { name: /Your focus/ }).waitFor();
  await noOverflow();
  await page.screenshot({ path: 'artifacts/desktop-overview.png', fullPage: true });
  await command("Prepare me for tomorrow's client meeting with Acme Corp.");
  await page.getByRole('heading', { name: 'Quarterly success review' }).waitFor();
  assert.ok(await page.getByRole('region', { name: 'Previous meeting records' }).isVisible());
  await page.getByRole('button', { name: 'Complete Validate SSO callback fix locally' }).click();
  assert.equal(await page.getByRole('button', { name: 'Reopen Validate SSO callback fix locally' }).getAttribute('aria-pressed'), 'true');
  await page.screenshot({ path: 'artifacts/desktop-meeting.png', fullPage: true });
  await command("Investigate why Acme Corp's product usage dropped.");
  await page.getByRole('region', { name: 'Product adoption' }).waitFor();
  assert.equal(await page.locator('.workspace-grid > section').first().getAttribute('aria-label'), 'Product adoption');
  await command('Show only the last 14 days.');
  assert.equal(await page.getByLabel('Date window', { exact: true }).inputValue(), '14');
  await command('Compare this with the previous period.');
  await page.getByText('Previous 14 days', { exact: true }).waitFor();
  await command('Move the usage chart to the top.');
  await page.screenshot({ path: 'artifacts/desktop-usage.png', fullPage: true });
  await command('Show this information as a table instead.');
  assert.equal(await page.locator('tbody tr').count(), 14);
  await page.getByRole('button', { name: 'Active users', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  assert.equal((await download).suggestedFilename(), 'kairos-usage.csv');
  await command('Focus on unresolved issues.');
  assert.equal(await page.locator('.workspace-grid > section').first().getAttribute('aria-label'), 'Issues & blockers');
  assert.equal(await page.locator('.issue-list').getByText('Export timezone mismatch').count(), 0);
  await command('Review projects that are falling behind schedule.');
  await page.getByRole('heading', { name: 'Asset library migration', exact: true }).waitFor();
  assert.equal(await page.locator('.workspace-grid > section').first().getAttribute('aria-label'), 'Projects behind schedule');
  assert.equal(await page.locator('.projects-list .project').count(), 3);
  await page.screenshot({ path: 'artifacts/desktop-projects.png', fullPage: true });
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await command('Prepare for a client meeting');
  await page.getByRole('region', { name: 'Clarification required' }).waitFor();
  await page.getByRole('button', { name: 'Prepare for Nova Studio meeting', exact: true }).click();
  await page.getByRole('heading', { name: 'Creative operations sync' }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await page.screenshot({ path: 'artifacts/mobile-meeting.png', fullPage: true });
  await command('Investigate Acme product usage');
  await page.getByRole('region', { name: 'Product adoption' }).waitFor();
  await noOverflow();
  await page.screenshot({ path: 'artifacts/mobile-usage.png', fullPage: true });
  await page.getByRole('button', { name: 'Save workspace to account' }).click();
  await page.getByText('Demo mode works without an account.', { exact: false }).waitFor();
  await page.getByRole('button', { name: 'Close account panel' }).click();
  await page.keyboard.press('Control+k');
  assert.equal(await page.getByRole('textbox', { name: 'Describe your goal' }).evaluate(el => el === document.activeElement), true);
  assert.deepEqual(errors, []);
  console.log('PASS: three scenarios, task actions, 14-day filter, comparison, reorder, table sort/export, unresolved issues, clarification, Nova scope, mobile overflow, account guidance, keyboard shortcut. No page errors.');
} catch (error) {
  await page.screenshot({ path: 'artifacts/smoke-failure.png', fullPage: true });
  console.error('Page errors:', errors);
  console.error('Visible headings:', await page.locator('h1,h2').allTextContents());
  throw error;
} finally { await browser.close(); }
