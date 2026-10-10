# Repository guidance

- `main` is the only public deployment branch: `/` redirects to `/blog/` and only the static blog is published. `dev` contains the experimental chat homepage and local Python/ChatGPT tools. Keep chat code and credentials out of the `main` deployment. Make shared blog fixes on `main` and bring them into `dev` deliberately; do not merge the experimental homepage into `main` to publish a blog update.

- This is a pnpm 10.11.0 / Turborepo monorepo. Run dependency installation from the repository root.
- `apps/blog` originated as a byte-identical import and now includes owner-authorized accessibility improvements. Preserve article wording, images, and overall design unless the user requests changes. The public AI editor must never modify it. Do not let unrelated shared-package changes alter blog behavior.
- The original blog package name is `personal-blog`. Use `pnpm build:blog` and `pnpm dev:blog` from the root.
- `pnpm verify:blog-import` compares the blog against the imported baseline. It is an import audit, not a prohibition on future owner-authorized writing. Do not silently regenerate the baseline to hide differences.
- Add independently deployable applications under `apps/`, backend services under `services/`, and reusable packages under `packages/`. Use explicit `workspace:*` dependencies; do not import across application internals.
- Keep application deployment scopes separate. The future public AI editor must not receive repository write access, blog files, blog deployment credentials, or authority to alter shared dependencies used by the blog.
- The experimental homepage and local ChatGPT OAuth editor exist only on `dev`. Never expose the local OAuth server publicly. Production on `main` serves only static blog files. Repository instructions are not an enforced runtime security boundary.
- Validate the affected packages through Turborepo. No remote repository or production deployment is configured yet.

## Accessibility

- Aim to meet WCAG 2.2 Level AA across the entire project, including embedded content and every interactive state.
- Prefer shared layouts, components, styles, and build-time validation so accessibility fixes apply to future pages automatically. Use semantic HTML, matching visible/accessibility labels, meaningful alternatives, keyboard support, visible focus, sufficient contrast, responsive reflow, and reduced-motion support.
- Preserve content and visual design when making accessibility fixes; do not silently replace author-provided image descriptions or article text.
- Run `pnpm test:a11y` for blog UI changes. Automated checks are only part of an audit: also check keyboard operation, zoom/text spacing, motion, and relevant assistive technologies. Record untested criteria honestly; do not claim conformance from an automated pass alone.
- See `docs/accessibility-audit.md` for coverage, findings, and remaining verification limits. The import manifest remains historical and must not be rewritten to conceal authorized changes.
