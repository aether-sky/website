# Branch workflow

| Branch | Root page | Purpose |
| --- | --- | --- |
| `main` | Redirect to `/blog/` | The only public deployment branch; static blog |
| `dev` | Experimental chat and editable iframe | Local development; never publish this branch |

The initial split preserves the current blog updates on both branches and the full homepage implementation on `dev`. Local virtual environments, OAuth credentials, dependency caches, generated builds, and scratch files are not committed. Those ignored files can remain on disk when switching branches; a release must never copy the whole checkout.

Use `git switch main` for blog publishing, or `git switch dev` for chat development. Commit your work before switching. Start the chat with `pnpm dev:site:live` on `dev`; stop the local server before switching branches.

Make new blog-only fixes on `main`, then cherry-pick the relevant commits onto `dev`. Deployment configuration and root workspace commands differ intentionally: avoid a blanket merge or copying one branch's root configuration over the other. Promoting the chat is a separate, explicit release decision after its production boundaries are implemented.

No Git remote is configured at this initial split. After adding a remote, push both branches, make `main` the default branch, and restrict any future production automation to `refs/heads/main`. Do not upload `.local-auth`, `.env`, the repository, or Python tools with the public static files.
