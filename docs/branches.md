# Branch workflow

| Branch | Root page | Purpose |
| --- | --- | --- |
| `main` | Redirect to `/blog/` | The only public deployment branch; static blog |
| `dev` | Experimental chat and editable iframe | Local development; never publish this branch |

The initial split preserves the current blog updates on both branches and the full homepage implementation on `dev`. Local virtual environments, OAuth credentials, dependency caches, generated builds, and scratch files are not committed. Those ignored files can remain on disk when switching branches; a release must never copy the whole checkout.

Use `git switch main` for blog publishing, or `git switch dev` for chat development. Commit your work before switching. Start the chat with `pnpm dev:site:live` on `dev`; stop the local server before switching branches.

Make new blog-only fixes on `main`, then cherry-pick the relevant commits onto `dev`. Deployment configuration and root workspace commands differ intentionally: avoid a blanket merge or copying one branch's root configuration over the other. Promoting the chat is a separate, explicit release decision after its production boundaries are implemented.

The Git remote is `https://github.com/aether-sky/website.git`. Push both branches and make `main` the default branch. The GitHub Actions workflow on `main` restricts publication to `refs/heads/main`; configure its production environment and restricted upload account using [the CI/CD guide](cicd-and-domain.md). Do not upload `.local-auth`, `.env`, the repository, or chat Python tools with the public static files.
