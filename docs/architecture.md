# Application boundaries

`main` contains the Astro blog and static deployment tools. Its public root redirects to `/blog/`. Node and pnpm are build tools; the public server needs only a static web server. There is no public chat endpoint, Python worker, OAuth callback, or LLM credential on this branch.

`dev` contains the separate trusted chat shell and loopback Python service with owner-only ChatGPT testing. The public editor, private review queue, and approved-page rotation remain unreleased. See that branch's local LLM and guardrail documents for the current implementation and its limits.

The blog's source, article content, and artwork are shared intentionally between the branches. Future AI editing must have no repository write access, blog mounts, deployment credentials, or tools that can change shared dependencies used by the blog. Repository documentation is not a runtime security boundary.

Applications belong in `apps/`, backend services in `services/`, and reusable code in `packages/`. Build and deploy independent applications separately. Release artifacts contain only the explicitly selected built files, never an entire working directory with ignored local files.
