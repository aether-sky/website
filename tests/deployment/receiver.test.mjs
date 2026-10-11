import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

test('restricted deployment receiver rejects hostile uploads', { skip: !process.env.DEPLOY_PYTHON && 'Set DEPLOY_PYTHON to run Python receiver tests' }, () => {
  const result = spawnSync(process.env.DEPLOY_PYTHON, ['-B', 'tests/deployment/test_receive.py'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
