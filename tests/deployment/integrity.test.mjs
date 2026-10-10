import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
test('server-side checksum verifier accepts the build and rejects corruption or extra files', { skip: !process.env.DEPLOY_BASH }, () => {
  const source = readFileSync(path.join(root, '.release/latest.txt'), 'utf8').trim();
  const verify = dir => spawnSync(process.env.DEPLOY_BASH, ['infra/vps/verify-release.sh', dir.replaceAll('\\', '/')], { cwd: root, encoding: 'utf8' });
  const good = verify(source);
  assert.equal(good.status, 0, good.stderr + good.stdout);
  for (const bad of ['corrupt', 'extra', 'absolute-path']) {
    const dir = mkdtempSync(path.join(os.tmpdir(), 'release-integrity-'));
    cpSync(source, dir, { recursive: true });
    if (bad === 'corrupt') writeFileSync(path.join(dir, 'public/blog/index.html'), 'tampered');
    if (bad === 'extra') writeFileSync(path.join(dir, 'public/blog/private.txt'), 'unlisted');
    if (bad === 'absolute-path') writeFileSync(path.join(dir, 'SHA256SUMS'), '0'.repeat(64) + '  /etc/passwd\n');
    assert.notEqual(verify(dir).status, 0, bad);
  }
});
