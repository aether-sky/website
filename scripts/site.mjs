import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
const action = process.argv[2];
if (!['build', 'dev', 'dev-live'].includes(action)) throw new Error('Expected build, dev or dev-live');
function run(args, env = {}) {
  const result = spawnSync(process.execPath, args, { stdio: 'inherit', env: { ...process.env, ...env } });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
if (action === 'build') {
  run(['node_modules/turbo/bin/turbo', 'run', 'build', '--filter=personal-blog', '--filter=@website/home-service'], { BLOG_BASE: '/blog' });
} else {
  // Fail before starting either service when the main port is already occupied.
  const probe = createServer();
  await new Promise((resolve, reject) => probe.once('error', () => reject(new Error('Port 8000 is in use. Stop the existing homepage server first.'))).listen(8000, '127.0.0.1', resolve));
  await new Promise(resolve => probe.close(resolve));
  run(['scripts/setup-home.mjs']);
  run(['node_modules/turbo/bin/turbo', 'run', 'build', '--filter=@website/home-service']);

  const blogPort = Number(process.env.BLOG_DEV_PORT || 4325);
  if (!Number.isInteger(blogPort) || blogPort < 1024 || blogPort > 65535 || blogPort === 8000) throw new Error('BLOG_DEV_PORT must be a local port from 1024 to 65535 other than 8000.');
  process.env.BLOG_BASE = '/blog';
  const blogRoot = fileURLToPath(new URL('../apps/blog/', import.meta.url));
  const requireBlog = createRequire(new URL('../apps/blog/package.json', import.meta.url));
  const requireAstro = createRequire(requireBlog.resolve('astro'));
  const viteClient = fileURLToPath(new URL('../client/env.mjs', pathToFileURL(requireAstro.resolve('vite'))));
  const { dev } = await import(pathToFileURL(requireBlog.resolve('astro')).href);
  const blog = await dev({ root: blogRoot, base: '/blog',
    server: { host: '127.0.0.1', port: blogPort },
    vite: { server: { strictPort: true,
      // HTTP goes through Python; HMR connects straight to the loopback watcher.
      ws: { host: '127.0.0.1', port: blogPort, clientPort: blogPort },
      fs: { allow: [blogRoot] },
    } },
  });
  const venv = fileURLToPath(new URL(`../services/home/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`, import.meta.url));
  const home = spawn(existsSync(venv) ? venv : process.env.PYTHON || 'python', [
    'services/home/server.py', '--static-dir', 'apps/home/src', '--blog-dev-port', String(blogPort),
    '--blog-dev-client-file', viteClient,
    '--port', '8000', '--parent-stdin', ...(action === 'dev-live' ? ['--live'] : []),
  ], { stdio: ['pipe', 'inherit', 'inherit'], windowsHide: true });
  // Closing stdin asks Python to exit cleanly (including the Windows venv
  // launcher). It also exits if this parent crashes and closes the pipe.
  let stopping = false;
  async function stop() {
    if (stopping) return;
    stopping = true;
    home.stdin.end();
    await blog.stop();
  }
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
  home.stdin.on('error', () => {}); // A child that already exited closed the pipe.
  home.once('error', async error => { console.error(error.message); process.exitCode = 1; await stop(); });
  home.once('exit', async code => { process.exitCode = stopping ? 0 : code ?? 1; await stop(); });
  console.log('Blog watch is running. Homepage: http://127.0.0.1:8000/ · Blog: http://127.0.0.1:8000/blog/');
}
