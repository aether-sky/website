import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import imageAttributes from './scripts/image-attributes.mjs';
export default defineConfig({
  site: process.env.SITE_URL || 'http://localhost:4324',
  output: 'static',
  trailingSlash: 'always',
  devToolbar: { enabled: false },
  markdown: { processor: unified({ smartypants: false, rehypePlugins: [imageAttributes] }) }
});
