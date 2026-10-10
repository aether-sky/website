# Homepage verification — October 10, 2026

Environment: Windows, Python 3.12.14, Node 24.19.0, pnpm 10.11.0,
Turborepo 2.11.7, Playwright 1.64.0, installed Microsoft Edge (Chromium).

## Executed checks

| Check | Result |
| --- | --- |
| `pnpm build:site` | Passed: home static assets, Python syntax, blog with `/blog` base |
| `pnpm exec turbo run build test --filter=@website/home-service` | Build/catalog validation and 64 service tests passed, including OAuth, headerless/malformed streams, authored task refusals, hint routing, HTML compiler, lifecycle and blog-proxy tests |
| `pnpm exec turbo run test:ui --filter=@website/home-service` | 20 existing browser tests passed; all 5 new live-path tests passed in a targeted rerun after fixing their corpus file path |
| `pnpm eval:home:guardrails` | 46 real-model request cases ready; full corpus not scored |
| Real OAuth and inference | Saved local-app sign-in successfully used `gpt-6.1-sol`. After the persona update, the exact Fibonacci prompt produced the 48-character authored task refusal with no frame change. Earlier transport testing also verified an accepted visual edit and denial of an executable iframe script. |
| Live browser regression | All 6 live-path tests passed after correcting explicit color routing, including task refusal, capability questions, vague change hints and unchanged iframe when no edit is requested. All 20 demo/browser tests passed in the preceding full run. |
| Combined watcher | Real Edge browser loaded the blog, article and development assets through port 8000, connected HMR to loopback 4325, and automatically updated a temporary Astro page after its file changed. The temporary page was removed. Ctrl+C released both listeners. |
| Repeatable setup and one-command launch | Repaired the environment after setup attempted to recreate an in-use interpreter. `pnpm dev:home:live` now checks dependencies, builds through Turbo and starts successfully. Repeated setup while the server runs passes without changing interpreter/configuration hashes, including with an unusable system `PYTHON`; all 55 service tests pass. |
| `pnpm test:a11y --output home-preview-artifacts/blog-check --reporter=line` | 51 passed; 16 failures in concurrently added `adventure.spec.mjs` from unresolved axe contrast checks over gradients |
| Desktop/mobile visual inspection | Reviewed 1440px desktop and 390px mobile, including the canvas after scrolling into view |
| Copied persona integrity | Source and destination SHA-256 hashes match |

The blog theme changes and adventure tests appeared during separate work in this
shared checkout and were preserved. The 16 failures occurred at the assertion
that axe's `incomplete` findings are empty: gradients prevented automated contrast
determination. This requires manual verification, not a claim of passing contrast.
The original `blog.spec.mjs` suite's 49 tests passed, along with two adventure
interaction tests. This task does not claim to have completed that theme audit.

Homepage and standalone blog builds now have independent output directories:
`apps/blog/dist-site` and `apps/blog/dist`. Homepage test artifacts use
`home-test-results`, visual-review artifacts use `home-preview-artifacts`, and
the homepage test server uses port 4397. Another local preview occupied port
4390, which caused a readiness timeout before that port was changed.

## Homepage coverage

- Streamed greeting in a dedicated chat region, with no header, navigation menu,
  shortcuts, or initial destination links. The composer contains actual editable
  text: "I hate your website...". Sending it prompts a sympathetic color suggestion.
- The initial color suggestion requires acceptance. Visitors choose subsequent
  edits themselves; no major edit volunteers a feature list. Explicit capability
  questions reveal a vague hint; asking what can change never edits. Unrelated
  tasks and unsafe requests use short authored refusals. Explicit blog/GitHub/portfolio requests redirect to
  fixed destinations; bio/contact replies stay in chat. Negated or incidental
  destination mentions do not redirect.
- Preset edits, opaque-origin iframe, empty sandbox, and reset outside the frame.
  Reset clears chat/introduction, restores factory HTML, and cancels pending
  edits; stale output cannot overwrite the restored state. It also restores the
  prefilled message and restarts the conversation. Canceled or incomplete edits
  do not advance state.
- TOML-authored replies, transitions, and Easter eggs: every egg's positive and
  negative examples, all haunted reply variants, priority/tie order, core-request
  precedence, once-only/unlimited behavior, and bounded seen IDs. Catalog loading
  rejects malformed files, unknown actions, invalid references, contradictory
  examples, and duplicate IDs. Catalog files are not publicly served.
- Browser verification of the haunted reply preserving a pending edit, firing
  once per conversation, returning after reset, and not consuming the egg when
  its stream is stopped or incomplete.
- Plain-text rendering of hostile chat strings, rejected active markup and
  navigation attributes, encoded markup staying text, bounded fragment size,
  node count/depth, and strict request validation.
- Script, parent-DOM, popup, form, CSS URL, and image-exfiltration probes injected
  below the validator to independently exercise browser enforcement. CSS/image
  attempts fail with CSP errors and never reach the network interceptor.
- Cancellation, incomplete streams, startup failure/retry, path traversal,
  private-file exclusion, origin/Host restrictions, and active-reply limits.
- Keyboard skip link, reset and composer, Shift+Enter, visible focus, focusable
  scrolling chat, forced colors, reduced-motion preference, 200% text enlargement,
  text spacing, and 320/768/1440 CSS-pixel reflow.
- Axe A/AA scans of the shell at all three widths and all four layouts, with
  color variations exercised across seven preset documents;
  `/blog` links, images, embeds, feed, sitemap, and canonicals.

The empty sandbox blocks scripts and timers, including timers needed by axe.
Shell scans therefore use axe's non-recursive mode. Each exact validated preset
document is scanned separately in a network-denied browser context; the real
iframe's permissions are never loosened. These checks support the limited demo,
not arbitrary generated HTML.

## Limits

The local editor adds 44 HTML goldens, a forced-allow malicious-model suite,
500 deterministic Hypothesis examples, browser reparsing of accepted goldens,
OAuth/JWT validation, DPAPI round-trip verification, refresh rotation, cancellation,
no unsolicited discovery checks, and local settings accessibility checks. See
[local-llm.md](local-llm.md) for the diagram, exact boundary and evaluation commands.
The browser model fixture deliberately approves everything; it proves neither
real classifier accuracy nor real-account entitlement. Signed JWT tests use
locally generated test keys, not production credentials.

No NVDA/JAWS/VoiceOver review, Firefox/WebKit testing, actual browser-zoom UI
audit, formal WCAG conformance assessment, production penetration test, sustained fuzzing,
load/DoS test, or full golden-set live-model evaluation was performed. The 200% text test enlarges
computed font sizes and does not replace a manual zoom audit. Axe does not cover
every accessibility criterion.

The Python server is a loopback development transport. Local ChatGPT OAuth,
owner-browser gating and a restrictive HTML5/CSS compiler are implemented.
Isolated editor/render workers, per-candidate content and
accessibility audits, durable review queue, public owner authentication,
approved-only rotation, production rate/cost limits, and deployment remain
unverified or planned. See [homepage-guardrails.md](homepage-guardrails.md)
for the behavior and adversarial-release plan. No universal safety or WCAG
conformance claim is made from these results.

The transport regression reproduced valid SSE with no Content-Type header.
The client now validates the body and completion rather than requiring that
header. Two visual drafts were correctly rejected for unsupported CSS; clarifying
the editor prompt's exhaustive property list and adding a valid example yielded
an accepted draft. The HTML validator was not loosened. These small live checks
do not establish classifier accuracy or an edit acceptance rate.
