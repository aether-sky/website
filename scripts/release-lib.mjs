import { createHash } from 'node:crypto';
import { copyFileSync, lstatSync, mkdirSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';

const extensions = new Set(['.html', '.css', '.js', '.xml', '.txt', '.json', '.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.pdf', '.mp4', '.webm']);

export function publicOrigin(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.pathname !== '/' || url.search || url.hash ||
      !url.hostname.includes('.') || url.hostname.length > 253 ||
      !url.hostname.split('.').every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) {
    throw new Error('Use a public HTTPS origin without a path, port, query, or credentials.');
  }
  return url.origin;
}

export function assertMain(branch) {
  if (branch !== 'main') throw new Error('Only main may build a public release. The dev chat is local only.');
}

export function filesBelow(root, prefix = '') {
  if (!lstatSync(root).isDirectory() || lstatSync(root).isSymbolicLink()) throw new Error('Release root must be a real directory.');
  return readdirSync(root).sort().flatMap(name => {
    if (name.startsWith('.') || !/^[A-Za-z0-9_.-]+$/.test(name)) throw new Error(`Unsupported public filename: ${name}`);
    const full = path.join(root, name);
    const stat = lstatSync(full);
    if (stat.isSymbolicLink()) throw new Error('Symlinks are not permitted in public artifacts.');
    if (stat.isDirectory()) return filesBelow(full, prefix + name + '/');
    if (!stat.isFile()) throw new Error('Only ordinary files may be published.');
    return [prefix + name];
  });
}

export function copyBlog(build, destination) {
  // The only application input is the blog's built artifact, never the checkout.
  const files = filesBelow(build);
  for (const name of files) {
    if (!extensions.has(path.extname(name).toLowerCase())) throw new Error(`Unsupported public file: ${name}`);
    const target = path.join(destination, name);
    mkdirSync(path.dirname(target), { recursive: true });
    copyFileSync(path.join(build, name), target);
  }
  if (!files.includes('index.html') || !files.includes('rss.xml')) throw new Error('Incomplete blog build.');
  return files;
}

export function digest(file) {
  return createHash('sha256').update(readFileSync(file)).digest('hex');
}
