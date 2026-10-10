import { cpSync, mkdirSync } from 'node:fs';
mkdirSync(new URL('./dist/', import.meta.url), { recursive: true });
for (const file of ['index.html', 'home.css', 'home.js', 'local.html', 'local.js', 'local.css']) {
  cpSync(new URL(`./src/${file}`, import.meta.url), new URL(`./dist/${file}`, import.meta.url));
}
console.log('Home assets built in apps/home/dist');
