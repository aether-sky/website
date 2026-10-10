# Repository guidance

- This is a pnpm 10.11.0 / Turborepo monorepo. Run dependency installation from the repository root.
- `apps/blog` is an unchanged import of the user's existing Astro blog, including its uncommitted article and animation updates. Do not modify it unless the user explicitly requests a blog change. Do not let unrelated shared-package changes alter blog behavior.
- The original blog package name is `personal-blog`. Use `pnpm build:blog` and `pnpm dev:blog` from the root.
- `pnpm verify:blog-import` compares the blog against the imported baseline. It is an import audit, not a prohibition on future owner-authorized writing. Do not silently regenerate the baseline to hide differences.
- Add independently deployable applications under `apps/`, backend services under `services/`, and reusable packages under `packages/`. Use explicit `workspace:*` dependencies; do not import across application internals.
- Keep application deployment scopes separate. The future public AI editor must not receive repository write access, blog files, blog deployment credentials, or authority to alter shared dependencies used by the blog.
- The AI editor and homepage are planned, not implemented. Repository instructions are not an enforced runtime security boundary.
- Validate the affected packages through Turborepo. No remote repository or production deployment is configured yet.
