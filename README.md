# Website

A pnpm / Turborepo monorepo for a personal website and its future applications. The first application is the existing Astro blog, imported unchanged with its original Git history and current uncommitted article/animation updates.

## Setup

Use Node.js 24 LTS and pnpm 10.11.0. From this directory:

```sh
pnpm install --frozen-lockfile
pnpm verify:blog-import
pnpm build
pnpm dev:blog
```

The blog runs at http://127.0.0.1:4324/. If the original blog preview is still using that port, stop it first or choose another port with `pnpm --filter personal-blog dev --port 4325`.

## Commands

| Command | Purpose |
| --- | --- |
| `pnpm dev` | Start all applications that have a development task |
| `pnpm build` | Build all applications with Turborepo dependency ordering and caching |
| `pnpm dev:blog` | Start only the blog |
| `pnpm build:blog` | Build only the blog and its workspace dependencies |
| `pnpm preview:blog` | Serve the blog's existing production build |
| `pnpm blog:new "My next article"` | Create a new blog draft when the owner wants to write |
| `pnpm verify:blog-import` | Compare the blog's files to the original import snapshot |

The import audit will report legitimate future article changes too. Its baseline documents this migration; it is not part of every build and should not be silently reset.

## Layout

```text
apps/blog/       Existing Astro blog (package name: personal-blog)
services/       Future backend services
packages/       Future shared packages
infra/          Future deployment and routing configuration
docs/           Architecture and import provenance
scripts/        Repository maintenance tools
```

Add future applications, including the landing page, directly under `apps/`. Each workspace package needs a unique package name and its own scripts. Use `workspace:*` for dependencies on local packages. Keep each app independently buildable and deployable; share code only when there is a concrete consumer.

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

The current blog expects to be served at the root of its own origin. Prefer a blog subdomain; serving it under `/blog` would require changes to its configuration and links. No remote repository or deployment is configured by this setup.

## AI editing boundary

The homepage and public AI editor are not implemented yet. Their planned boundary is described in [docs/architecture.md](docs/architecture.md). A shared Git repository does not grant the editor permission to modify the blog.

## Import provenance

[docs/blog-import.json](docs/blog-import.json) records the original commit, working-tree status, file sizes, and SHA-256 digests for all imported source and asset files. The source repository was copied, not changed. Generated builds, dependencies, caches, local secrets, and nested Git metadata were not imported.

The original commit remains in this repository's history; the migration commit relocates its files under `apps/blog` and includes the uncommitted updates. The original blog README is preserved under `apps/blog/README.md`; its standalone repository and hosting statements describe the pre-import project.

Tooling references: [pnpm workspaces](https://pnpm.io/workspaces), [Turborepo configuration](https://turborepo.dev/docs/reference/configuration).
