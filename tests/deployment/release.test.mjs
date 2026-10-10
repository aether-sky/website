import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { assertMain, copyBlog, filesBelow, publicOrigin } from '../../scripts/release-lib.mjs';

test('public releases require main and an HTTPS origin without injected configuration', () => {
  assert.doesNotThrow(() => assertMain('main'));
  for (const branch of ['dev', '', 'detached', 'main\nextra']) assert.throws(() => assertMain(branch));
  assert.equal(publicOrigin('https://aether-sky.cloud/'), 'https://aether-sky.cloud');
  for (const origin of ['http://example.com', 'https://example.com/blog', 'https://a:b@example.com',
    'https://example.com:444', 'https://example.com/?secret=x', 'https://example.com/#x', 'https://localhost',
    'https://bad_label.example', 'https://-bad.example']) assert.throws(() => publicOrigin(origin));
});

function fixture() {
  const root = mkdtempSync(path.join(os.tmpdir(), 'static-blog-test-'));
  const build = path.join(root, 'blog');
  mkdirSync(build);
  writeFileSync(path.join(build, 'index.html'), '<h1>Blog</h1>');
  writeFileSync(path.join(build, 'rss.xml'), '<rss/>');
  return { root, build, destination: path.join(root, 'published/blog') };
}

test('only the blog build is copied, even with adjacent local chat and secrets', () => {
  const { root, build, destination } = fixture();
  mkdirSync(path.join(root, 'home'));
  writeFileSync(path.join(root, 'home/home.js'), 'chat');
  writeFileSync(path.join(root, '.env'), 'secret');
  copyBlog(build, destination);
  assert.deepEqual(filesBelow(destination), ['index.html', 'rss.xml']);
  assert.equal(readFileSync(path.join(destination, 'index.html'), 'utf8'), '<h1>Blog</h1>');
});

test('unexpected private files and source code inside the build fail publication', () => {
  for (const name of ['.env', '.git', 'server.py', 'credentials.bin', 'bad\nname.html']) {
    const { build, destination } = fixture();
    // Windows cannot represent newline paths. The other cases run everywhere.
    if (name.includes('\n') && process.platform === 'win32') continue;
    writeFileSync(path.join(build, name), 'never publish');
    assert.throws(() => copyBlog(build, destination));
  }
});

test('directory links cannot pull files outside the artifact into a release', () => {
  const { root, build, destination } = fixture();
  const privateDir = path.join(root, 'private');
  mkdirSync(privateDir);
  writeFileSync(path.join(privateDir, 'token.txt'), 'private');
  symlinkSync(privateDir, path.join(build, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
  assert.throws(() => copyBlog(build, destination), /Symlinks/);
});
