# Application boundaries

## Implemented

- One local Git repository with pnpm workspaces and Turborepo.
- The original Astro blog under `apps/blog`, including its existing article, images, animation, style, routes, and package files.
- Root development/build commands, local task caching, import verification, and space for additional applications and services.

## Planned

- `apps/home`: the main landing page, with a permanent link to the blog and a public AI prompt.
- `services/editor`: generate and validate constrained changes, store accepted revisions, and immediately update the shared homepage after checks pass.
- `packages/site-spec`: approved page components, edit schemas, and validation rules once the editor is built.
- Independent deployment configuration for each application and service.

## Blog protection

The public editor must only be able to change approved homepage data. It must not have repository write credentials, blog source/assets, blog deployment access, or tools capable of changing shared code used by the blog. Keep the blog's runtime and editable homepage data separate. Preserve a fixed blog link outside the visitor-editable region.

Future runtime controls must enforce these rules even when the model emits a prohibited request. Instructions in this repository and directory organization are documentation, not a security boundary.

## Growth

Applications live under `apps/`, backend services under `services/`, and reusable code under `packages/`. Prefer explicit package dependencies over cross-application imports. JavaScript/TypeScript projects join the pnpm workspace; services in other languages can use their own tooling and optionally expose task scripts for Turborepo.

Build and deploy affected applications and their dependencies. Do not make a change to one independent application require every other application to be deployed.
