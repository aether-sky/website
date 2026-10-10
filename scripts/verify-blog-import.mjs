import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const blog = path.join(root, 'apps', 'blog');
const manifest = JSON.parse(await readFile(path.join(root, 'docs', 'blog-import.json'), 'utf8'));
const ignoredDirectories = new Set(['.git', 'node_modules', 'dist', '.astro', '.turbo']);

async function listFiles(directory, prefix = '') {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (ignoredDirectories.has(entry.name)) continue;
    if (entry.name === '.DS_Store' || entry.name === 'Thumbs.db') continue;
    if ((entry.name === '.env' || entry.name.startsWith('.env.')) && entry.name !== '.env.example') continue;
    const relative = prefix + entry.name;
    if (entry.isDirectory()) result.push(...await listFiles(path.join(directory, entry.name), relative + '/'));
    else if (entry.isFile()) result.push(relative);
    else throw new Error(`Unexpected non-regular file: ${relative}`);
  }
  return result;
}

const actual = new Set(await listFiles(blog));
const problems = [];
for (const expected of manifest.files) {
  if (!actual.delete(expected.path)) {
    problems.push(`Missing: ${expected.path}`);
    continue;
  }
  const content = await readFile(path.join(blog, expected.path));
  const digest = createHash('sha256').update(content).digest('hex');
  if (digest !== expected.sha256) problems.push(`Changed: ${expected.path}`);
}
for (const extra of actual) problems.push(`Added: ${extra}`);
if (problems.length) {
  console.error('Blog differs from the import baseline:\n' + problems.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`Verified ${manifest.files.length} blog files: byte-for-byte identical to the imported working tree.`);
}
