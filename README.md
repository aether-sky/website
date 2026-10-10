# Website

This is **main**, the public blog branch. The experimental chat homepage and Python/ChatGPT tools live on **dev**. Only `main` may be published. See [branch workflow](docs/branches.md).

## Publish

Follow [the Linode/Debian runbook](docs/vps-deployment.md) for the $12 Linode VPS. Commit blog and deployment changes on `main`, then run `pnpm release:site https://aether-sky.cloud` (substitute your domain). It produces a blog-only archive; the server redirects `/` to `/blog/`. No Python, LLM key, or coding agent is deployed. Nothing is uploaded automatically.

Use `pnpm build:site https://aether-sky.cloud` for a local artifact without the clean-checkout requirement, and `pnpm test:release` for release-boundary checks through Turborepo.

## Local development

Use Node.js 24 LTS and pnpm 10.11.0. Install from the repository root:

```sh
pnpm install --frozen-lockfile
pnpm dev:blog
```

The standalone blog runs at http://127.0.0.1:4324/. `pnpm build:blog` builds it through Turborepo; `pnpm preview:blog` previews the build. Set `SITE_URL` to the public origin for correct canonical and RSS URLs. The blog supports a `/blog` base for the combined public site as well as standalone root hosting.

## Layout

- `apps/blog`: Astro blog, package name `personal-blog`.
- `tests/accessibility`: automated blog interaction and accessibility coverage.
- `docs`: architecture, branch workflow, design notes, and verification limits.
- `infra`: deployment configuration.
- `services`, `packages`: reserved for independent services and reusable packages.

The root workspace and lockfile are authoritative. Install dependencies here, not in `apps/blog`. The blog's nested lock/workspace files are historical import artifacts. Use explicit `workspace:*` dependencies for future shared packages; never import across application internals.

## Blog editing and verification

Use `pnpm blog:new "My next article"` to start a draft. Classic and Storybook appearances share the same articles and accessible controls; see [design notes](docs/myst-riven-style.md).

Run `pnpm test:a11y` after blog UI changes. On Windows with Edge installed, set `$env:PLAYWRIGHT_CHANNEL = 'msedge'`; otherwise install Playwright Chromium first. See [the accessibility audit](docs/accessibility-audit.md) for coverage and unverified manual criteria. Automated passing tests do not establish full WCAG conformance.

`pnpm verify:blog-import` compares against the original import. It intentionally reports subsequent owner-authorized changes; never regenerate [the import baseline](docs/blog-import.json) to conceal them.
