# Application boundaries

## Implemented

- One local Git repository with pnpm workspaces and Turborepo.
- The original Astro blog under `apps/blog`, including its existing article, images, animation, style, routes, and package files.
- Root development/build commands, local task caching, import verification, and space for additional applications and services.
- `apps/home`: trusted static shell with streaming demo chat, isolated editable preview, and factory reset.
- `services/home`: loopback-only Python preview service. It consumes the home's built static artifact; no application-internal imports. It optionally serves a read-only blog build at `/blog/` for local integration.
- `pnpm build:site` builds the home and blog's `/blog` mode through Turborepo. `pnpm dev:home` builds and serves them locally.

## Planned

- A live streaming chat provider with the copied Tadaima voice and an owner-approved public résumé summary.
- `services/editor`: isolated HTML generation/validation with no repository or blog access. Accepted changes affect only the requesting visitor until the owner approves an immutable revision for random public delivery.
- Private review queue, authenticated owner dashboard, approved-only rotation, and production transport.
- Independent deployment configuration for each application and service.

## Blog protection

The public editor must only be able to change approved homepage data. It must not have repository write credentials, blog source/assets, blog deployment access, or tools capable of changing shared code used by the blog. Keep the blog's runtime and editable homepage data separate. The trusted chat can offer a fixed blog destination when requested; the interface intentionally has no top navigation menu. Reset remains outside the visitor-editable region.

Future runtime controls must enforce these rules even when the model emits a prohibited request. Instructions in this repository and directory organization are documentation, not a security boundary.

The full behavior, HTML validation, queue lifecycle, threat model, and release test plan is in [homepage-guardrails.md](homepage-guardrails.md). The current Python server is local preview infrastructure, not the future editor worker or production security boundary.

## Growth

Applications live under `apps/`, backend services under `services/`, and reusable code under `packages/`. Prefer explicit package dependencies over cross-application imports. JavaScript/TypeScript projects join the pnpm workspace; services in other languages can use their own tooling and optionally expose task scripts for Turborepo.

Build and deploy affected applications and their dependencies. Do not make a change to one independent application require every other application to be deployed.
