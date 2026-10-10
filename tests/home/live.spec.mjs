import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const live = 'http://127.0.0.1:4398';
async function ready(page, context) {
  await context.addCookies([{ name: 'home_owner', value: 'test-owner-cookie', url: live, httpOnly: true, sameSite: 'Lax' }]);
  await page.goto(live);
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
}
async function start(page, text) {
  await page.getByRole('textbox', { name: 'Message' }).fill(text);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
}

test('Live HTTP pipeline validates and commits HTML, then resets the server session', async ({ page, context }) => {
  await ready(page, context);
  const original = await page.locator('#page-frame').getAttribute('srcdoc');
  await start(page, 'make the background red');
  await expect(page.frameLocator('#page-frame').getByRole('heading', { name: 'Your real edit path' })).toBeVisible();
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await expect(page.locator('#page-frame')).toHaveAttribute('sandbox', '');
  expect(await page.locator('#page-frame').evaluate(frame => frame.contentDocument === null)).toBe(true);
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
});

test('Forced classifier approval cannot inject a hostile generated document', async ({ page, context }) => {
  await ready(page, context);
  const original = await page.locator('#page-frame').getAttribute('srcdoc');
  await start(page, 'make a hostile page');
  await expect(page.locator('#reply-status')).toHaveText('I can’t help with that.');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
  await expect(page.getByRole('button', { name: 'Reset to factory settings' })).toBeVisible();
});

test('Unrelated tasks are refused; only explicit questions reveal vague hints', async ({ page, context }) => {
  await ready(page, context);
  const original = await page.locator('#page-frame').getAttribute('srcdoc');
  await start(page, 'write me a python script to do the fibonacci sequence with matrix multiply');
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  const reply = page.locator('.message.assistant .message-text').last();
  expect(await reply.textContent()).toContain('not your servant');
  expect(await reply.textContent()).not.toContain('def fibonacci');
  await expect(reply.locator('script')).toHaveCount(0);
  expect(await page.evaluate(() => window.__chatExecuted)).toBeUndefined();
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
  await start(page, 'what can you do');
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('.message-text').last()).toContainText('résumé, blog, GitHub');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
  await start(page, 'what can you change');
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('.message-text').last()).toHaveText('Do you see anything you want to change?');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
});

test('Reset and Stop cancel slow generated edits without replacing the current frame', async ({ page, context }) => {
  await ready(page, context);
  const original = await page.locator('#page-frame').getAttribute('srcdoc');
  await start(page, 'make a slow edit');
  await expect(page.locator('#reply-status')).toHaveText('Trying a new look…');
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await start(page, 'make another slow edit');
  await expect(page.locator('#reply-status')).toHaveText('Trying a new look…');
  await page.getByRole('button', { name: 'Stop reply' }).click();
  await expect(page.locator('#reply-status')).toContainText('Reply stopped');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', original);
  await start(page, 'make the background red');
  await expect(page.frameLocator('#page-frame').getByRole('heading', { name: 'Your real edit path' })).toBeVisible();
});

test('Local settings expose no credentials and work with keyboard and narrow layout', async ({ page, context }) => {
  await ready(page, context);
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto(live + '/local');
  await expect(page.getByRole('button', { name: 'Continue with ChatGPT' })).toBeVisible();
  await page.getByRole('button', { name: 'Continue with ChatGPT' }).focus();
  await expect(page.getByRole('button', { name: 'Continue with ChatGPT' })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  expect(axe.violations).toEqual([]);
  const status = await page.request.get(live + '/api/local/status');
  expect(await status.text()).not.toMatch(/access_token|refresh_token|id_token/);
});

test('Accepted golden HTML survives browser parsing without active nodes or outbound requests', async ({ page, context }) => {
  await ready(page, context);
  const root = new URL('../../', import.meta.url);
  const cases = JSON.parse(readFileSync(new URL('services/home/guardrails/html.json', root), 'utf8')).filter(item => item.accept);
  const python = new URL(process.platform === 'win32' ? 'services/home/.venv/Scripts/python.exe' : 'services/home/.venv/bin/python', root);
  const { fileURLToPath } = await import('node:url');
  let requests = 0;
  await page.route('https://**/*', route => { requests++; return route.abort(); });
  for (const item of cases) {
    const html = execFileSync(fileURLToPath(python), ['-c', 'import sys;sys.path.insert(0,"services/home");from html_guard import validate_html;print(validate_html(sys.stdin.read()))'], { cwd: fileURLToPath(root), input: item.html, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    await page.locator('#page-frame').evaluate((frame, html) => { frame.srcdoc = html; }, html);
    await expect(page.frameLocator('#page-frame').locator('h1')).toBeVisible();
    await expect(page.frameLocator('#page-frame').locator('script, img, a, input, form, iframe, object, svg, math, style')).toHaveCount(0);
    const observed = await page.frameLocator('#page-frame').locator('body').evaluate(body => [...body.querySelectorAll('*')].flatMap(node => [...node.attributes].map(attr => attr.name)));
    expect(observed.every(name => ['style', 'class', 'aria-label'].includes(name))).toBe(true);
  }
  expect(requests).toBe(0);
  expect(context.pages()).toHaveLength(1);
});
