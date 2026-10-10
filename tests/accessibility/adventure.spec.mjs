import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { checkPaperContrast } from './paper-contrast.mjs';

const dist = fileURLToPath(new URL('../../apps/blog/dist/', import.meta.url));
const routes = readdirSync(dist, { recursive: true }).filter(name => name.endsWith('.html') && !name.replaceAll('\\', '/').startsWith('animations/')).map(name => '/' + name.replaceAll('\\', '/').replace(/index\.html$/, ''));

for (const route of routes) for (const theme of ['dark', 'light']) for (const width of [1280, 320]) {
  test(`Adventure accessibility: ${route} ${theme} ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(theme => { localStorage.setItem('blog-style', 'adventure'); localStorage.setItem('blog-theme', theme); }, theme);
    await page.goto(route);
    for (const image of await page.locator('img').all()) { await image.scrollIntoViewIfNeeded(); await image.evaluate(element => element.decode()); }
    for (const frame of await page.locator('iframe').all()) await frame.scrollIntoViewIfNeeded();
    for (const frame of page.frames()) if (frame.url().includes('/animations/')) await expect(frame.locator('canvas')).toHaveAttribute('data-layers', '9');
    await expect(page.locator('html')).toHaveAttribute('data-style', 'adventure');
    const result = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
    expect(result.violations).toEqual([]);
    await checkPaperContrast(page, result.incomplete);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.addStyleTag({ content: '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  });
}

test('Style is keyboard selectable, persistent, and independent of color mode', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-style', 'classic');
  const picker = page.getByRole('combobox', { name: 'Style', exact: true });
  await picker.focus();
  await page.keyboard.press('Home');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Tab');
  await expect(page.locator('html')).toHaveAttribute('data-style', 'adventure');
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await page.goto('/sitemap/');
  await expect(page.locator('html')).toHaveAttribute('data-style', 'adventure');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(picker).toHaveValue('adventure');
  await picker.selectOption('classic');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-style', 'classic');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('Style control still works if preference storage is unavailable', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } }); });
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Style', exact: true }).selectOption('adventure');
  await expect(page.locator('html')).toHaveAttribute('data-style', 'adventure');
});
