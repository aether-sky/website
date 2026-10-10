import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import config from '../../apps/blog/astro.config.mjs';
import { checkPaperContrast } from './paper-contrast.mjs';

const markdown = [
  '[Example](https://example.com/){target="_blank"}',
  '[Ordinary](https://example.com/ordinary)',
  '[Custom](https://example.com/custom){target="_blank" rel="nofollow opener" aria-label="Custom resource"}',
  '`[Code](https://example.com/){target="_blank"}`',
].join('\n\n');

for (const style of ['classic', 'adventure']) for (const theme of ['dark', 'light']) {
  test(`Markdown new-tab links: ${style} ${theme}`, async ({ page }) => {
    const renderer = await config.markdown.processor.createRenderer({ syntaxHighlight: false });
    const { code } = await renderer.render(markdown);
    await page.addInitScript(({ style, theme }) => {
      localStorage.setItem('blog-style', style);
      localStorage.setItem('blog-theme', theme);
    }, { style, theme });
    await page.goto('/posts/i-gave-chatgpt-another-try/');
    // Exercise compiled Markdown inside the real shared layout without publishing a fixture post.
    await page.locator('.prose').evaluate((element, html) => { element.innerHTML = html; }, code);
    const link = page.getByRole('link', { name: 'Example', exact: true });
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener');
    await expect(link).toHaveAccessibleDescription('(opens in new tab)');
    await expect(link.locator('.new-tab-notice')).toBeHidden();
    const custom = page.getByRole('link', { name: 'Custom resource', exact: true });
    await expect(custom).toHaveAccessibleDescription('(opens in new tab)');
    await expect(custom).toHaveAttribute('rel', 'nofollow noopener');
    await expect(page.getByRole('link', { name: 'Ordinary', exact: true })).not.toHaveAttribute('target');
    await expect(page.locator('.prose .new-tab-notice')).toHaveCount(2);
    await expect(page.locator('.prose code')).toHaveText('[Code](https://example.com/){target="_blank"}');
    const result = await new AxeBuilder({ page }).include('.prose').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(result.violations).toEqual([]);
    if (style === 'adventure') await checkPaperContrast(page, result.incomplete);
    else expect(result.incomplete).toEqual([]);
    await page.context().route('https://example.com/**', route => route.fulfill({ body: 'Example destination' }));
    await link.focus();
    const popupPromise = page.waitForEvent('popup');
    await page.keyboard.press('Enter');
    const popup = await popupPromise;
    await popup.waitForLoadState();
    expect(await popup.evaluate(() => window.opener === null)).toBe(true);
    await popup.close();
  });
}
