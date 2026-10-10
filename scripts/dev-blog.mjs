import { fileURLToPath } from 'node:url';

// Run Astro in this process: no Turbo worker or Windows .cmd intermediary.
const blog = new URL('../apps/blog/', import.meta.url);
const cli = new URL('node_modules/astro/bin/astro.mjs', blog);
const args = process.argv.slice(2);
const hasOption = name => args.some(arg => arg === name || arg.startsWith(`${name}=`));
process.chdir(fileURLToPath(blog));
process.argv = [process.execPath, fileURLToPath(cli), 'dev',
  ...(!hasOption('--host') ? ['--host', '127.0.0.1'] : []),
  ...(!hasOption('--port') ? ['--port', '4324'] : []),
  ...args];
await import(cli.href);
