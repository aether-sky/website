# Website

This is the **dev** branch: the chat homepage and local ChatGPT experiments live here. Only **main** is published; its root redirects to `/blog/` and its deployment contains the static blog only. See [branch workflow](docs/branches.md).

A pnpm / Turborepo monorepo for a personal website, a Python-served homepage interface, and an Astro blog. The first application is the existing Astro blog, originally imported unchanged with its Git history and working-tree updates. It now includes owner-authorized accessibility improvements; the import manifest remains a historical record.

## Setup

Use Node.js 24 LTS, pnpm 10.11.0, and Python 3.12 or newer. If Python is not on PATH, set `PYTHON` to its executable path. From this directory:

```sh
pnpm install --frozen-lockfile
pnpm dev:site:live
```

The combined site runs at http://127.0.0.1:8000/, with the blog at http://127.0.0.1:8000/blog/. Astro watches blog files and automatically reloads changed pages. Open the one-use settings link printed in the terminal for local ChatGPT editing. Use `pnpm dev:site` for demo chat. Ctrl+C stops both services. Stop an existing port-8000 preview before starting. The watcher uses loopback port 4325 internally (`BLOG_DEV_PORT` can override it); standalone `pnpm dev:blog` still uses http://127.0.0.1:4324/.

## Commands

| Command | Purpose |
| --- | --- |
| `pnpm dev:site` / `pnpm dev:home` | Start the Python homepage with demo chat and the Astro blog watcher |
| `pnpm setup:home` | Reuse or create the homepage virtual environment and install missing pinned dependencies |
| `pnpm dev:site:live` / `pnpm dev:home:live` | Check dependencies, build the home package, and run local ChatGPT editing plus the blog watcher |
| `pnpm eval:home:guardrails` | Describe the opt-in request-classifier golden evaluation |
| `pnpm build:site` | Build the homepage service and blog with its /blog base path |
| `pnpm test:home` | Run Python validation, request, and boundary tests through Turborepo |
| `pnpm test:home:ui` | Build /blog mode and run homepage browser, isolation, and accessibility tests |
| `pnpm dev` | Start all applications that have a development task |
| `pnpm build` | Build all applications with Turborepo dependency ordering and caching |
| `pnpm dev:blog` | Start only the blog directly with Astro |
| `node scripts/dev-blog.mjs` | Start only the blog without Windows batch wrappers; recommended on Windows for clean Ctrl+C shutdown |
| `pnpm build:blog` | Build only the blog and its workspace dependencies |
| `pnpm preview:blog` | Serve the blog's existing production build |
| `pnpm blog:new "My next article"` | Create a new blog draft when the owner wants to write |
| `pnpm verify:blog-import` | Compare the blog's files to the original import snapshot |

The import audit will report legitimate future article changes too. Its baseline documents this migration; it is not part of every build and should not be silently reset.

## Layout

```text
apps/blog/       Existing Astro blog (package name: personal-blog)
apps/home/       Trusted homepage shell (built static artifact)
services/home/   Python interface preview and Tadaima persona
services/        Future isolated editor and other backend services
packages/       Future shared packages
infra/          Future deployment and routing configuration
docs/           Architecture and import provenance
scripts/        Repository maintenance tools
```

Add future applications directly under `apps/`. `services/home` depends explicitly on `@website/home` for build ordering and consumes only its dist artifact, not application internals. Each workspace package needs a unique package name and its own scripts. Use `workspace:*` for dependencies on local packages. Keep each app independently buildable and deployable; share code only when there is a concrete consumer.

## Dependency management

Always run installs from this repository root. The root `pnpm-workspace.yaml` and `pnpm-lock.yaml` are authoritative for monorepo installs. The blog's original package manifest, lockfile, and single-package workspace file remain byte-identical inside `apps/blog` to preserve the import. Do not run a separate install inside that directory for monorepo development.

Astro and its Markdown processor retain the original pinned versions and dependency resolutions. Turborepo is pinned at 2.11.7. The root workspace allows dependency build scripts only for `esbuild` and `sharp`.

Turborepo caches `dist/` output, hashes `SITE_URL` and environment-file inputs for builds, and leaves development and preview tasks uncached. Remote caching is not configured.

## Blog deployment

Build from the root with `pnpm build:blog`, then deploy `apps/blog/dist`. Set `SITE_URL` to the actual blog origin before building so canonical and RSS URLs are correct. For example, in PowerShell:

```powershell
$env:SITE_URL = 'https://blog.example.com'
pnpm build:blog
```

The blog defaults to the root of its own origin for standalone use. `pnpm build:site` sets `BLOG_BASE=/blog` and builds links, article asset paths, RSS, and canonical paths for the main site. Set `SITE_URL` to the public origin (without `/blog`) before that build. Standalone builds write `apps/blog/dist`; `/blog` builds write `apps/blog/dist-site`, keeping concurrent previews independent. No remote repository or production deployment is configured. In production, route `/blog/*` to the independent static blog deployment and `/` to the trusted Python web service; never mount the blog in a live editor worker.

## AI editing boundary

Optional local ChatGPT editing is now implemented. See [local setup, pipeline
diagram, and golden evaluations](docs/local-llm.md). It adds owner-only OAuth,
a tool-less request classifier/editor, server-owned session state and a separate
HTML5/CSS allowlist compiler. Account authorization and real inference have been
smoke-tested; the public queue and rotation remain a future milestone.
The paragraph below describes the default demo mode.

The homepage has a streaming demo, preset canvas changes, a sandboxed iframe, and factory reset. There is no header or shortcut menu. The composer starts with editable text, "I hate your website...". Tadaima is a coy webpage character: unrelated tasks get the "not your servant" reply; denied requests get "I can’t help with that." Only explicit capability questions reveal a vague résumé/blog/GitHub/edit hint. Completed edits do not advertise capabilities. Explicit blog/GitHub requests redirect; the bio appears in chat. The résumé is still pending. The original Claude Tadaima voice is copied under `services/home/prompts/`. See [docs/homepage-guardrails.md](docs/homepage-guardrails.md) for the public release plan and [docs/homepage-verification.md](docs/homepage-verification.md) for evidence and limits. A shared Git repository does not grant the editor permission to modify the blog.

Replies and the guided edit sequence live in TOML under `services/home/behaviors`, with one file per Easter egg. Ask “Is this website haunted?” to try the example. See the [dialogue authoring guide](services/home/behaviors/README.md) for adding replies, triggers, and edit steps. Build and startup validate the catalog; action permissions remain in Python.

The home build is deliberately small and has no frontend framework dependencies. The combined development runner serves `apps/home/src` directly: refresh for home HTML/CSS/JS changes. Blog edits hot-reload through Astro. Python, prompt or TOML changes require restarting the runner. `pnpm build:site` still creates independent static home and `/blog` artifacts. The Python server and development proxy are local tools, not a production server.

## Import provenance

[docs/blog-import.json](docs/blog-import.json) records the original commit, working-tree status, file sizes, and SHA-256 digests for all imported source and asset files. The source repository was copied, not changed. Generated builds, dependencies, caches, local secrets, and nested Git metadata were not imported.

The original commit remains in this repository's history; the migration commit relocates its files under `apps/blog` and includes the uncommitted updates. The original blog README is preserved under `apps/blog/README.md`; its standalone repository and hosting statements describe the pre-import project.

Tooling references: [pnpm workspaces](https://pnpm.io/workspaces), [Turborepo configuration](https://turborepo.dev/docs/reference/configuration).

## Accessibility

Aim for WCAG 2.2 AA throughout the project. The blog uses shared layout/style fixes and an automatically generated site map. Read [the audit](docs/accessibility-audit.md) for findings, criterion coverage, and remaining manual verification.

Run `pnpm exec playwright install chromium` once, then `pnpm test:a11y` for the blog or `pnpm test:home:ui` for the homepage. On Windows with Microsoft Edge installed, use `$env:PLAYWRIGHT_CHANNEL = 'msedge'` instead of downloading Chromium. The command builds the blog and tests every generated HTML route, including embedded media, both themes, keyboard controls, reduced motion, and narrow layouts. Review `playwright-report/index.html` after a run. New articles automatically join the scans; new interactions still need suitable behavior tests and manual review.

`pnpm verify:blog-import` intentionally reports authorized edits since the original import, including these fixes. Do not reset that baseline to make it pass.

## Blog appearance

The shared blog header includes a **Style** selector: **Classic** keeps the original design; **Storybook** uses a book-inspired interface: a two-page linking-book index, a top-bound reading journal, black surroundings, and gray Windows-style menu controls. See [the screenshot references and design notes](docs/myst-riven-style.md). Classic remains the default. The choice is saved locally in `blog-style` and is independent of the existing `blog-theme` light/dark preference. Both styles apply automatically to all pages using the shared blog layout. Article content and the animation artwork are unchanged by the style switch.

Adventure styles live in `apps/blog/src/styles/adventure.css` and are scoped to `data-style="adventure"`. Keep new skin rules scoped so switching back restores Classic. `pnpm test:a11y` includes both styles, mobile layouts, preference persistence, keyboard switching, and unavailable browser storage.
