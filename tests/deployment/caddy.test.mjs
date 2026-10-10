import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = fileURLToPath(new URL('../../', import.meta.url));
test('real Caddy serves the blog and rejects chat/private routes', { skip: !process.env.CADDY_BIN }, async () => {
  const release = readFileSync(path.join(root, '.release/latest.txt'), 'utf8').trim();
  const probe = createServer();
  probe.listen(0, '127.0.0.1');
  await once(probe, 'listening');
  const port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  const address = `http://127.0.0.1:${port}`;
  const env = { ...process.env, SITE_ADDRESS: address, SITE_ROOT: path.join(release, 'public').replaceAll('\\', '/') };
  const adapted = spawnSync(process.env.CADDY_BIN, ['adapt', '--config', path.join(root, 'infra/vps/Caddyfile'), '--adapter', 'caddyfile'], { env, encoding: 'utf8' });
  assert.equal(adapted.status, 0, adapted.stderr);
  const config = JSON.parse(adapted.stdout);
  config.admin = { disabled: true }; // No machine-wide admin listener in this test.
  const temp = mkdtempSync(path.join(os.tmpdir(), 'caddy-static-test-'));
  const configFile = path.join(temp, 'caddy.json');
  writeFileSync(configFile, JSON.stringify(config));
  const server = spawn(process.env.CADDY_BIN, ['run', '--config', configFile], { env, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
  let errors = '';
  server.stderr.on('data', data => { errors = (errors + data).slice(-12000); });
  try {
    let ready = false;
    for (let i = 0; i < 60; i++) {
      try { ready = (await fetch(address + '/healthz')).ok; } catch {}
      if (ready) break;
      if (server.exitCode !== null) throw new Error(errors);
      await delay(100);
    }
    assert.ok(ready, errors);
    for (const route of ['/', '/index.html', '/?from=visitor']) {
      const response = await fetch(address + route, { redirect: 'manual' });
      assert.equal(response.status, 302);
      assert.equal(response.headers.get('location'), '/blog/');
      assert.equal(response.headers.get('cache-control'), 'no-store');
    }
    assert.equal((await fetch(address + '/blog', { redirect: 'manual' })).status, 308);
    const page = await fetch(address + '/blog/');
    assert.equal(page.status, 200);
    assert.equal(page.headers.get('x-content-type-options'), 'nosniff');
    const html = await page.text();
    const origin = JSON.parse(readFileSync(path.join(release, 'release.json'))).origin;
    assert.ok(html.includes(origin + '/blog/'));
    const paths = [...html.matchAll(/(?:src|href)="(\/blog\/[^"#?]*)/g)].map(match => match[1]);
    for (const route of new Set(paths)) assert.equal((await fetch(address + route)).status, 200, route);
    const rss = await (await fetch(address + '/blog/rss.xml')).text();
    assert.ok(rss.includes(origin + '/blog/posts/'));
    for (const route of ['/local', '/local.js', '/home.js', '/api/config', '/api/chat', '/auth/callback', '/.env', '/.git/config', '/blog/.env', '/blog/%2e%2e/.env', '/release.json', '/deploy/Caddyfile']) {
      assert.equal((await fetch(address + route)).status, 404, route);
    }
    assert.equal((await fetch(address + '/api/chat', { method: 'POST', body: '{}' })).status, 404);
  } finally {
    if (server.exitCode === null) {
      const exited = once(server, 'exit');
      server.kill();
      await exited;
    }
  }
});
