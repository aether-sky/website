import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertMain, copyBlog, digest, filesBelow, publicOrigin } from './release-lib.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const inputs = ['apps/blog', 'infra/vps', 'scripts/public-site.mjs', 'scripts/release-lib.mjs',
  'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'turbo.json', '.gitattributes', '.gitignore'];
process.chdir(root);
function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed: ${result.stderr || 'see output above'}`);
  return result.stdout?.trim();
}

try {
  const [action, requestedOrigin] = process.argv.slice(2);
  if (!['build', 'release', 'check'].includes(action) || process.argv.length > 5) throw new Error('Usage: node scripts/public-site.mjs build|release|check https://your-domain');
  if (action !== 'check') assertMain(run('git', ['branch', '--show-current']));
  const origin = publicOrigin(requestedOrigin || process.env.SITE_URL || '');
  if (action === 'release' && run('git', ['status', '--porcelain', '--untracked-files=all', '--', ...inputs])) {
    throw new Error('Commit blog and deployment inputs on main before creating a release.');
  }
  const commit = run('git', ['rev-parse', 'HEAD']);
  run(process.execPath, ['node_modules/turbo/bin/turbo', 'run', 'build', '--filter=personal-blog'], {
    stdio: 'inherit', env: { ...process.env, BLOG_BASE: '/blog', SITE_URL: origin },
  });
  const output = path.join(root, '.release');
  mkdirSync(output, { recursive: true });
  if (lstatSync(output).isSymbolicLink()) throw new Error('Release output must not be a symlink.');
  const stage = mkdtempSync(path.join(output, 'site-'));
  const publicDir = path.join(stage, 'public');
  copyBlog(path.join(root, 'apps/blog/dist-site'), path.join(publicDir, 'blog'));
  // Fallback for static previews. Caddy supplies the real HTTP redirect.
  writeFileSync(path.join(publicDir, 'index.html'), '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="refresh" content="0;url=/blog/"><title>Sky’s blog</title><a href="/blog/">Continue to the blog</a></html>\n');
  mkdirSync(path.join(stage, 'deploy'));
  for (const name of ['Caddyfile', 'activate.sh', 'rollback.sh', 'verify-release.sh']) {
    copyFileSync(path.join(root, 'infra/vps', name), path.join(stage, 'deploy', name));
  }
  writeFileSync(path.join(stage, 'COMMIT'), commit + '\n');
  writeFileSync(path.join(stage, 'DOMAIN'), new URL(origin).hostname + '\n');
  writeFileSync(path.join(stage, 'release.json'), JSON.stringify({ branch: action === 'check' ? 'ci-check' : 'main', commit, origin, kind: 'static-blog', builtAt: new Date().toISOString() }, null, 2) + '\n');
  const sums = filesBelow(stage).map(name => `${digest(path.join(stage, name))}  ${name}`).join('\n') + '\n';
  writeFileSync(path.join(stage, 'SHA256SUMS'), sums);
  // Reject accidental exposure of a chat app even when ignored dev artifacts remain.
  if (filesBelow(publicDir).some(name => name !== 'index.html' && !name.startsWith('blog/'))) throw new Error('Unexpected public application.');
  const html = readFileSync(path.join(publicDir, 'blog/index.html'), 'utf8');
  if (!html.includes(origin + '/blog/')) throw new Error('Blog canonical origin did not match the release.');
  if (action === 'release') {
    assertMain(run('git', ['branch', '--show-current']));
    if (run('git', ['rev-parse', 'HEAD']) !== commit || run('git', ['status', '--porcelain', '--untracked-files=all', '--', ...inputs])) {
      throw new Error('Release inputs changed during the build; commit and retry.');
    }
    const archive = path.join(output, `site-${commit.slice(0, 12)}.tar.gz`);
    if (existsSync(archive) && lstatSync(archive).isSymbolicLink()) throw new Error('Archive must not be a symlink.');
    run('tar', ['-czf', archive, '-C', stage, 'public', 'deploy', 'COMMIT', 'DOMAIN', 'release.json', 'SHA256SUMS']);
    console.log(`Release: ${archive}\nSHA-256: ${digest(archive)}`);
  }
  writeFileSync(path.join(output, 'latest.txt'), stage + '\n');
  console.log(`Static preview: ${stage}\nOnly public/ is served. Nothing has been uploaded.`);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
