import { test, expect } from '@playwright/test';
import { checkPaperContrast } from './paper-contrast.mjs';

test('paper contrast excludes foreground outlines but still rejects a matching background', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('blog-style', 'adventure'));
  await page.goto('/');
  await page.locator('main').evaluate(main => {
    main.innerHTML = '<p id="contrast-probe" style="display:inline-block;color:#000;background:#fff;outline:20px solid #000;outline-offset:-10px">Contrast probe</p>';
  });
  await checkPaperContrast(page, []);
  await page.locator('#contrast-probe').evaluate(element => { element.style.background = '#000'; });
  await expect(checkPaperContrast(page, [])).rejects.toThrow('Rendered paper must meet contrast');
});
