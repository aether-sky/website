# Personal blog

A local Astro blog with Markdown articles and a static HTML build. Dark mode is the default. The first article preserves the supplied text and image order. Its title and archive description are editable frontmatter. Nothing has been published or connected to a remote repository.

## Run locally

Install Node.js 22.12+ (Node 24 recommended) and pnpm 10. Then:

```sh
pnpm install
pnpm dev
```

Open http://localhost:4324. `pnpm build` generates `dist/`; `pnpm preview` serves that build.

## Write another article

```sh
pnpm new-post "My next article"
```

Edit the resulting `src/content/posts/my-next-article.md`:

```yaml
---
title: "My next article"
description: "A short summary for the archive and RSS feed."
date: 2026-10-11
draft: true
---
```

Write standard Markdown below the frontmatter. Put images in `public/images/my-next-article/` and insert them with `![Alt text](/images/my-next-article/photo.png)`. Set `draft: false` to include a post in the site, archive, and RSS. Drafts are excluded in both dev and production. To preview an unpublished article locally, temporarily set it to false; switch it back before deploying. Dates sort newest first; `draft` is the publication switch, not a scheduler.

## Customize

- `src/site.ts`: blog name and description (currently the neutral name “Notes”).
- `src/styles/global.css`: the original restrained dark style and optional light theme.
- `src/layouts/Base.astro`: navigation, metadata, footer.
- `src/content/posts/`: articles. The filename determines the URL.
- `public/`: assets copied directly to the build.

## Host it anywhere

This site generates ordinary static files; no database or server runtime is needed. Use a host that can build Astro or upload `dist/` to any static web host. Serve at the root of a domain; subdirectory hosting requires configuring Astro's base and updating root-relative links.

Set the environment variable `SITE_URL` to your real origin, e.g. `https://blog.your-domain.com`, before building. This sets canonical and RSS URLs. Without it, local preview URLs are used. The `.env.example` file documents this variable; set it in your host's build environment or your shell:

```sh
SITE_URL=https://blog.your-domain.com pnpm build
```

PowerShell:

```powershell
$env:SITE_URL = 'https://blog.your-domain.com'
pnpm build
```

Build command: `pnpm install --frozen-lockfile && pnpm build`. Publish directory: `dist`. On Windows run those commands separately. Commit new articles and images, then rebuild/redeploy. With a Git-connected host, pushing commits can trigger the build automatically.

Documentation: https://docs.astro.build/en/guides/content-collections/
