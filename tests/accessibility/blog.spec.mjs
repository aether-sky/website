import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const dist = fileURLToPath(new URL('../../apps/blog/dist/', import.meta.url));
function htmlFiles(directory, prefix = '') {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => entry.isDirectory()
    ? htmlFiles(path.join(directory, entry.name), prefix + entry.name + '/')
    : entry.name.endsWith('.html') ? [prefix + entry.name] : []);
}
// Every built page joins the audit automatically when an article or route is added.
const routes = htmlFiles(dist).map(file => '/' + file.replace(/index\.html$/, ''));
const animation = '/animations/fifty.html';
const states = [...routes, animation + '?embed=1'];
const blogRoutes = routes.filter(route => !route.startsWith('/animations/'));
const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const spacing = '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';

async function ready(page, route) {
  await page.goto(route);
  // Load lazy images and embeds before checking layout and accessibility.
  for (const image of await page.locator('img').all()) {
    await image.scrollIntoViewIfNeeded();
    await image.evaluate(element => element.decode());
  }
  for (const iframe of await page.locator('iframe').all()) await iframe.scrollIntoViewIfNeeded();
  for (const frame of page.frames()) {
    if (frame.url().includes('/animations/')) await expect(frame.locator('canvas')).toHaveAttribute('data-layers', '9');
  }
}

for (const route of states) for (const theme of ['dark', 'light']) for (const width of [1280, 320]) {
  test(`WCAG A/AA scan: ${route} ${theme} ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(value => localStorage.setItem('blog-theme', value), theme);
    await ready(page, route);
    const result = await new AxeBuilder({ page }).withTags(tags).analyze();
    expect(result.violations, JSON.stringify(result.violations, null, 2)).toEqual([]);
    expect(result.incomplete, 'Review new incomplete axe checks manually').toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  });
}

for (const route of blogRoutes) {
  test(`Skip link and theme keyboard control: ${route}`, async ({ page }) => {
    await page.goto(route);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement.closest('main') !== null)).toBe(true);
    const theme = page.getByRole('button', { name: /Switch to light mode/ });
    await theme.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeFocused();
    await page.keyboard.press('Space');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });
}

for (const route of states) {
  test(`Text spacing and narrow reflow: ${route}`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await ready(page, route);
    for (const frame of page.frames()) await frame.addStyleTag({ content: spacing });
    for (const frame of page.frames()) {
      expect(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      const clipped = await frame.evaluate(() => [...document.querySelectorAll('h1,h2,p,button,label')].filter(element => {
        const css = getComputedStyle(element);
        return css.display !== 'none' && !element.classList.contains('sr-only') &&
          ((['hidden','clip'].includes(css.overflowX) && element.scrollWidth > element.clientWidth + 2) ||
           (['hidden','clip'].includes(css.overflowY) && element.scrollHeight > element.clientHeight + 2));
      }).map(element => element.outerHTML.slice(0,200)));
      expect(clipped).toEqual([]);
    }
  });
}

test('Animation alternative, keyboard controls, and layer announcements', async ({ page }) => {
  await ready(page, animation + '?embed=1');
  await expect(page.getByRole('img', { name: /Fifty playing an ocarina/ })).toBeVisible();
  await expect(page.locator('canvas')).toHaveAccessibleDescription(/silent, looping illustration/);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  const paused = await page.locator('canvas').getAttribute('data-time');
  await page.waitForTimeout(200);
  expect(await page.locator('canvas').getAttribute('data-time')).toBe(paused);
  await page.keyboard.press('Tab');
  const slider = page.getByRole('slider', { name: 'Motion', exact: true });
  await expect(slider).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveValue('1.1');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Fullscreen', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Inspect layers' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#layer-status')).toHaveText('Separated: books / drill curl / wing / body / flowing hair');
  await expect(page.getByRole('button', { name: 'Reassemble' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#layer-status')).toHaveText('Scene reassembled.');
});

test('Reduced motion is honored at load and when the preference changes', async ({ page }) => {
  await ready(page, animation);
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  expect(await page.locator('canvas').getAttribute('data-time')).toBe('0.00');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.reload();
  await expect(page.locator('canvas')).toHaveAttribute('data-layers', '9');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  const time = await page.locator('canvas').getAttribute('data-time');
  await page.waitForTimeout(200);
  expect(await page.locator('canvas').getAttribute('data-time')).toBe(time);
});

test('Fullscreen keeps playback controls available and restores focus', async ({ page }) => {
  await ready(page, animation + '?embed=1');
  await page.getByRole('button', { name: 'Fullscreen', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.contains(document.querySelector('.controls')))).toBe(true);
  await expect(page.getByRole('button', { name: 'Exit fullscreen' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('slider', { name: 'Motion' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true);
  await expect(page.getByRole('button', { name: 'Fullscreen', exact: true })).toBeFocused();
});

for (const route of states) {
  test(`Text can resize to 200%: ${route}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await ready(page, route);
    for (const frame of page.frames()) {
      // Double computed font sizes simultaneously, avoiding compounding inherited sizes.
      await frame.evaluate(() => {
        const sizes = [...document.querySelectorAll('body,body *')].map(element => [element, parseFloat(getComputedStyle(element).fontSize)]);
        for (const [element, size] of sizes) element.style.fontSize = `${size * 2}px`;
      });
      expect(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      for (const control of await frame.locator('button,input').all()) {
        await control.scrollIntoViewIfNeeded();
        await expect(control).toBeVisible();
      }
    }
  });
}

test('Site map provides working links to all published content', async ({ page }) => {
  await page.goto('/sitemap/');
  const links = await page.locator('main a').evaluateAll(elements => elements.map(element => new URL(element.href).pathname));
  for (const route of routes.filter(route => !['/sitemap/', '/404.html'].includes(route))) expect(links).toContain(route);
  for (const href of links) expect((await page.request.get(href)).ok()).toBe(true);
});

test('Animation remains operable in forced colors and landscape', async ({ page }) => {
  await page.emulateMedia({ forcedColors: 'active' });
  await page.setViewportSize({ width: 720, height: 320 });
  await ready(page, animation + '?embed=1');
  for (const control of await page.locator('button,input').all()) {
    await control.focus();
    await expect(control).toBeFocused();
    await expect(control).toBeInViewport();
    const outline = await control.evaluate(element => getComputedStyle(element).outlineStyle);
    expect(outline).not.toBe('none');
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});



for (const route of blogRoutes) {
  test(`Tab traversal, including embeds, never obscures focus: ${route}`, async ({ page }) => {
    await ready(page, route);
    const seen = new Set();
    let completed = false;
    for (let step = 0; step < 50; step++) {
      await page.keyboard.press('Tab');
      const focus = await page.evaluate(() => {
        let doc = document;
        while (doc.activeElement?.tagName === 'IFRAME') doc = doc.activeElement.contentDocument;
        const element = doc.activeElement;
        if (!element || element === doc.body) return null;
        const rect = element.getBoundingClientRect();
        const win = doc.defaultView;
        // Inline links may wrap: their overall bounding box includes empty space.
        const fragments = [...element.getClientRects()].filter(part =>
          part.width > 0 && part.height > 0 && part.bottom > 0 && part.top < win.innerHeight && part.right > 0 && part.left < win.innerWidth);
        return {
          key: doc.URL + '|' + element.outerHTML,
          visible: rect.bottom > 0 && rect.top < win.innerHeight && rect.right > 0 && rect.left < win.innerWidth,
          unobscured: fragments.some(part => {
            const x = (Math.max(0, part.left) + Math.min(win.innerWidth - 1, part.right)) / 2;
            const y = (Math.max(0, part.top) + Math.min(win.innerHeight - 1, part.bottom)) / 2;
            return element.contains(doc.elementFromPoint(x, y));
          }),
          outline: win.getComputedStyle(element).outlineStyle,
        };
      });
      if (!focus) continue;
      if (seen.has(focus.key)) { completed = true; break; }
      expect(focus.visible).toBe(true);
      expect(focus.unobscured).toBe(true);
      expect(focus.outline).not.toBe('none');
      seen.add(focus.key);
    }
    expect(completed, 'Keyboard focus should traverse the whole page and return to the start').toBe(true);
  });
}

