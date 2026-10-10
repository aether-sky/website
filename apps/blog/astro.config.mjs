import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import imageAttributes from './scripts/image-attributes.mjs';
import baseLinks from './scripts/base-links.mjs';
import remarkAttributes from 'remark-attributes';
import newTabLinks from './scripts/new-tab-links.mjs';
import remarkDirective from 'remark-directive';
import remarkTooltips from './scripts/remark-tooltips.mjs';
const base = process.env.BLOG_BASE || '/';
export default defineConfig({
  base,
  outDir: base === '/' ? './dist' : './dist-site',
  site: process.env.SITE_URL || 'http://localhost:4324',
  output: 'static',
  trailingSlash: 'always',
  devToolbar: { enabled: false },
  markdown: { processor: unified({ smartypants: false, remarkPlugins: [remarkDirective, remarkAttributes, remarkTooltips], rehypePlugins: [imageAttributes, [baseLinks, { base }], newTabLinks] }) }
});
