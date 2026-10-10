import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import config from '../../apps/blog/astro.config.mjs';
import { checkPaperContrast } from './paper-contrast.mjs';

test.use({ hasTouch: true });
for (const style of ['classic', 'adventure']) for (const theme of ['dark', 'light']) for (const width of [1280, 320]) {
  test(`Tooltip: ${style} ${theme} ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    const renderer = await config.markdown.processor.createRenderer({ syntaxHighlight: false });
    const { code } = await renderer.render('[Before](#main) :tooltip[artistic structure]{text="Composition, visual hierarchy, and narrative purpose. <em>This is text.</em>"} and :tooltip[another]{text="Second explanation"}');
    await page.addInitScript(({ style, theme }) => {
      localStorage.setItem('blog-style', style);
      localStorage.setItem('blog-theme', theme);
    }, { style, theme });
    await page.goto('/posts/i-gave-chatgpt-another-try/');
    await page.locator('.prose').evaluate((element, html) => { element.innerHTML = html; }, code);
    const trigger = page.getByRole('button', { name: 'artistic structure', exact: true });
    const tip = page.locator('#blog-tooltip-1');
    await expect(tip).toBeHidden();
    await expect(trigger).toHaveAccessibleDescription('Composition, visual hierarchy, and narrative purpose. <em>This is text.</em>');
    await page.getByRole('link', { name: 'Before', exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(trigger).toBeFocused();
    await expect(tip).toBeVisible();
    await expect(tip.locator('em')).toHaveCount(0);
    const bounds = await tip.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
    // Axe cannot resolve top-layer overlap for contrast. Check the opaque popup
    // colors directly, and run the normal contrast audit with the popup closed.
    const colors = await tip.evaluate(element => {
      const css = getComputedStyle(element);
      return { fg: css.color, bg: css.backgroundColor };
    });
    const rgb = value => value.match(/[\d.]+/g).map(Number);
    const background = rgb(colors.bg);
    expect(background[3] ?? 1).toBe(1);
    const luminance = values => values.slice(0, 3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const fg = luminance(rgb(colors.fg)), bg = luminance(background);
    expect((Math.max(fg, bg) + .05) / (Math.min(fg, bg) + .05)).toBeGreaterThanOrEqual(4.5);
    const openAudit = await new AxeBuilder({ page }).include('.prose').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).disableRules(['color-contrast']).analyze();
    expect(openAudit.violations).toEqual([]);
    expect(openAudit.incomplete).toEqual([]);
    await page.keyboard.press('Escape');
    await expect(tip).toBeHidden();
    await expect(trigger).toBeFocused();
    const audit = await new AxeBuilder({ page }).include('.prose').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(audit.violations).toEqual([]);
    if (style === 'adventure') await checkPaperContrast(page, audit.incomplete);
    else expect(audit.incomplete).toEqual([]);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'another', exact: true })).toBeFocused();
    await page.keyboard.press('Escape');
    await trigger.hover();
    await expect(tip).toBeVisible();
    await tip.hover();
    await page.waitForTimeout(200); // Longer than the pointer-leave grace period.
    await expect(tip).toBeVisible();
    await page.keyboard.press('Escape');
    await trigger.tap();
    await expect(tip).toBeVisible();
    await trigger.tap();
    await expect(tip).toBeHidden();
    await trigger.tap();
    await page.locator('h1').tap();
    await expect(tip).toBeHidden();
  });
}

test('Malformed tooltip syntax preserves the article text', async () => {
  const renderer = await config.markdown.processor.createRenderer({ syntaxHighlight: false });
  const { code } = await renderer.render('Before :tooltip[Missing explanation]("Hint") after.');
  expect(code).toContain('Before :tooltip[Missing explanation]("Hint") after.');
});
