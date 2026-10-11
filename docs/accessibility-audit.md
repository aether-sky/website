# Blog accessibility audit — WCAG 2.2 AA

Audit date: 2026-10-10. Repository: `C:/Users/sky/codex-projects/website`. Scope: the local production build of `apps/blog`, including every published HTML page, the error page, and the animation both standalone and embedded. This is a criterion-by-criterion engineering audit, not a formal conformance certification.

## Result

The identified implementation issues have been fixed. Automated scans and behavior tests pass in Microsoft Edge. All 55 WCAG 2.2 Level A and AA success criteria are accounted for below, including criteria that do not apply to this blog. No known implementation failure remains within the tested scope. End-to-end screen-reader testing and additional browser/device testing remain necessary before making an unqualified conformance claim.

The article Markdown was not edited by this audit. Existing and concurrent author edits were preserved. All five original PNG files and the embedded animation image payloads match their pre-audit versions. The layout, typography, palettes, and artwork remain intact. Small visible accessibility changes are a site-map link, standalone-player navigation, and moving the layer label from canvas pixels into resizable HTML below the controls.

## Pages and states

- `/`: blog index.
- `/posts/i-gave-chatgpt-another-try/`: the currently published article, including all four displayed illustrations and the lazy-loaded animation iframe.
- `/404.html`: error page.
- `/sitemap/`: generated navigation page added by this audit.
- `/animations/fifty.html`: standalone animation.
- `/animations/fifty.html?embed=1`: embedded player, also checked within its parent article.
- Dark/light themes; 1280px and 320px widths; 200% computed text sizing; increased text spacing; keyboard focus; play/pause; layer inspection/reassembly; fullscreen; initial and dynamically changed reduced-motion preference; landscape and forced-colors player operation.

The animation retains its intentionally dark artwork/player in either blog theme. External destinations and feed-reader rendering of `/rss.xml` are outside this HTML audit. No production deployment is configured, so deployed headers, routing, browser extensions, and hosting error pages were not tested.

## Findings and fixes

| Finding | Criteria | Resolution |
| --- | --- | --- |
| Visible “Motion” label was replaced by the accessible name “Animation intensity”. | 2.5.3 | Removed the overriding ARIA label; the native wrapping label supplies “Motion”. |
| Canvas label alone did not expose the illustration in the browser accessibility tree. | 1.1.1, 4.1.2 | Added an image role and a connected description of the scene, movement, and inspection behavior. |
| Layer information existed only as text drawn into canvas pixels. | 1.1.1, 1.4.4, 1.4.5, 4.1.3 | Moved the same label into real HTML with a persistent status region; reassembly also reports its result. Text can now resize, wrap, and be announced. |
| Fullscreen contained the canvas but excluded playback controls. | 2.1.1, 2.2.2 | Fullscreen now contains the player and its controls, allows scrolling when necessary, changes the button name, and restores focus on exit. |
| Load/error messages lacked status semantics and were hidden from assistive technology in embeds. | 4.1.3 | Added `role="status"` and atomic updates; embedded status is visually hidden while remaining available to assistive technology. |
| Skip navigation did not explicitly transfer DOM focus to main content. | 2.4.1, 2.4.3; robustness improvement | The shared layout now gives main `tabindex="-1"` and a visible focus outline. Tested Enter activation and subsequent Tab movement. |
| Standalone media lacked site navigation; navigation needed a second path that scales with more posts. | 2.4.5 | Added a shared footer site-map link, a generated list of published posts and standalone HTML animations, and standalone-player Blog/Site map links. Embedded-player navigation remains in the parent page. |
| The animation honored reduced motion only at initial load. | Motion-accessibility improvement beyond the basic pause requirement | Preference changes now pause it immediately. Explicit Play remains available. |
| Slider target height depended on the browser's small native control box. | 2.5.8; hardening | Set a minimum 24px input height while retaining native keyboard and pointer behavior. |

Changes are centralized in the shared layout/styles, generated navigation, and the single player used both standalone and embedded. Article-by-article markup changes were not necessary.

## Evidence and repeatable checks

`pnpm test:a11y` builds the blog through Turborepo and runs Playwright with axe. The suite discovers every built HTML route automatically, loads lazy images and iframes, and includes future published articles without adding individual test cases. It also exercises site-map links, theme controls, the Motion slider, playback, announcements, fullscreen focus, reduced motion, text spacing, text sizing, and keyboard traversal into and out of embeds. Tests and reports are located at:

- `playwright.a11y.config.mjs`
- `tests/accessibility/blog.spec.mjs`
- `playwright-report/index.html` after running the suite (generated, ignored by Git)

Environment: Windows, Edge 154.0.4258.53, Playwright 1.64.0, axe-core integration 4.13.0. Use `PLAYWRIGHT_CHANNEL=msedge` for the installed Edge browser, or install Playwright Chromium using `pnpm exec playwright install chromium`.

The final run contains 49 tests. Axe covers A/AA rules for WCAG 2.0, 2.1, and 2.2 and reports neither violations nor incomplete checks for the scanned states. The original automated scan also reported no violations: the label mismatch and missing canvas exposure were found through targeted accessibility-tree and source inspection. An axe pass is therefore not a substitute for the other checks.

The existing palettes already meet normal-text contrast: dark body/muted/link text approximately 13.72:1 / 7.09:1 / 8.73:1; light equivalents 14.09:1 / 5.60:1 / 7.45:1. Automated checks also cover the player's DOM text. Focus colors contrast with their backgrounds, underlines identify prose links, and the native slider exposes its value. Decorative separators are not essential control boundaries.

Rendered screenshots, DOM geometry, accessibility-tree snapshots, keyboard interactions, and source inspection supplemented automation. The 320 CSS-pixel reflow check represents the content width expected at 400% zoom on a 1280px viewport; actual browser-menu zoom was not exercised. Text-resize tests double computed font sizes without compounding inheritance. Forced-colors testing checks operability/focus, not a full visual review of every operating-system high-contrast palette.

## All A and AA criteria

“Reviewed” means no failure was identified using the stated evidence in the tested environment; it is not a cross-browser or assistive-technology certification. “Not applicable” means the relevant content or functionality is absent in this build. Criteria 4.1.2 and 4.1.3 have browser accessibility-tree evidence but retain the end-to-end assistive-technology limitation noted below. WCAG 2.2 removed the obsolete 4.1.1 Parsing criterion.

| Criterion | Level | Assessment and evidence |
| --- | --- | --- |
| 1.1.1 Non-text Content | A | Reviewed after fixes. Existing illustrations have author-provided alt text and surrounding context; canvas now has an exposed name/description. Artwork reviewed visually. |
| 1.2.1 Audio-only and Video-only (Prerecorded) | A | Reviewed conservatively for the silent looping illustration: the text alternative describes the scene and its changing visual behavior. No audio-only material. |
| 1.2.2 Captions (Prerecorded) | A | Not applicable: no recorded audio in synchronized media. |
| 1.2.3 Audio Description or Media Alternative (Prerecorded) | A | Not applicable: no synchronized audio/video media. The silent illustration is addressed above. |
| 1.2.4 Captions (Live) | AA | Not applicable: no live media. |
| 1.2.5 Audio Description (Prerecorded) | AA | Not applicable: no synchronized audio/video media. |
| 1.3.1 Info and Relationships | A | Reviewed. Semantic headings, lists, landmarks, article/time elements, linked label and slider, iframe title; axe and accessibility-tree inspection. |
| 1.3.2 Meaningful Sequence | A | Reviewed. DOM and visual reading order agree; content remains linear when narrowed. |
| 1.3.3 Sensory Characteristics | A | Reviewed. Labels/instructions do not require recognizing color, shape, sound, or screen position alone. Pointer motion is decorative. |
| 1.3.4 Orientation | AA | Reviewed. No orientation lock; responsive layout and landscape player checked. |
| 1.3.5 Identify Input Purpose | AA | Not applicable: no personal-information inputs. |
| 1.4.1 Use of Color | A | Reviewed. Prose links are underlined; controls have text labels and state changes use words, not color alone. |
| 1.4.2 Audio Control | A | Not applicable: no audio. |
| 1.4.3 Contrast (Minimum) | AA | Reviewed. Both palettes and player text pass scanned contrast checks; calculated palette ratios above. |
| 1.4.4 Resize Text | AA | Reviewed. Computed text sizes doubled across all routes/frames without horizontal overflow or hidden controls; canvas label replaced with HTML. Browser-menu zoom remains a separate verification item. |
| 1.4.5 Images of Text | AA | Reviewed after moving the functional canvas label into HTML. Remaining text within the illustrations is incidental artwork, not the mechanism for presenting article/UI text. |
| 1.4.10 Reflow | AA | Reviewed. All routes/embeds checked at 320 CSS pixels without page-level horizontal scrolling. Images scale; controls wrap. |
| 1.4.11 Non-text Contrast | AA | Reviewed. Visible focus contrasts with backgrounds; controls use readable text/native range affordances. Decorative borders are not relied on as the only control identification. |
| 1.4.12 Text Spacing | AA | Reviewed. Line height 1.5, paragraph spacing 2em, letter spacing .12em, word spacing .16em applied at narrow width; overflow/clipping checks pass. |
| 1.4.13 Content on Hover or Focus | AA | Not applicable: no author-created tooltips, popovers, or hover/focus-revealed content. |
| 2.1.1 Keyboard | A | Reviewed. Native links/buttons/range work with Tab, Shift+Tab, Enter, Space, and arrow keys; fullscreen retains controls. Pointer parallax is decorative and conveys no exclusive information. |
| 2.1.2 No Keyboard Trap | A | Reviewed. Focus traverses pages and embeds; fullscreen can be exited using its button; no modal traps. |
| 2.1.4 Character Key Shortcuts | A | Not applicable: no custom single-character shortcuts. |
| 2.2.1 Timing Adjustable | A | Not applicable: no user task time limits, session expiry, or timed data entry. |
| 2.2.2 Pause, Stop, Hide | A | Reviewed after fullscreen fix. Play/Pause stops automatic motion; time remains fixed when paused, including under reduced motion. |
| 2.3.1 Three Flashes or Below Threshold | A | Reviewed by animation source and rendered scene. Slow swaying, drifting, scowling, and small twinkles; no rapid broad-area flashes identified. No dedicated flash-analysis tool was run. |
| 2.4.1 Bypass Blocks | A | Reviewed. Shared skip link is first in tab order and now focuses main. Standalone player has no repeated block before its main content. |
| 2.4.2 Page Titled | A | Reviewed. All HTML routes have meaningful titles; iframe also has a descriptive title. |
| 2.4.3 Focus Order | A | Reviewed. Native DOM order follows reading order; skip and fullscreen focus behavior tested. |
| 2.4.4 Link Purpose (In Context) | A | Reviewed. Article titles, back links, Blog, Site map, RSS, and the animation link have understandable purposes in context. |
| 2.4.5 Multiple Ways | AA | Reviewed after navigation addition. Blog/archive links and generated site map provide routes to published content; standalone animation links back into the site. |
| 2.4.6 Headings and Labels | AA | Reviewed. Descriptive page/section headings and control labels, with one primary heading per standalone content page. Embedded media uses its parent heading/context. |
| 2.4.7 Focus Visible | AA | Reviewed. Explicit focus outlines on links/buttons/range; keyboard traversal and forced-colors player checked. |
| 2.4.11 Focus Not Obscured (Minimum) | AA | Reviewed. No sticky overlays; focused controls are visible during traversal, including embedded controls and fullscreen. |
| 2.5.1 Pointer Gestures | A | Reviewed. Controls require only a click/tap; native slider supports point selection. Decorative parallax does not require a path gesture to operate functionality. |
| 2.5.2 Pointer Cancellation | A | Reviewed. Native click/button/range behavior; no custom pointer-down activation of actions. |
| 2.5.3 Label in Name | A | Reviewed after Motion fix. Visible control text matches or is contained in accessible names; theme action names include the displayed mode. |
| 2.5.4 Motion Actuation | A | Not applicable: no device-motion controls. |
| 2.5.7 Dragging Movements | AA | Reviewed. Slider can be set using single-point selection or keyboard; no drag-only task. |
| 2.5.8 Target Size (Minimum) | AA | Reviewed. Player controls have adequate targets, range has 24px minimum height, and smaller text links have spacing or the inline-text exception. Axe target-size checks and geometry inspected. |
| 3.1.1 Language of Page | A | Reviewed. `lang="en"` on blog pages and player. |
| 3.1.2 Language of Parts | AA | Reviewed. English prose with proper names and an isolated borrowed term; no unmarked extended foreign-language passage. |
| 3.2.1 On Focus | A | Reviewed. Focusing controls does not navigate, submit, or change context. |
| 3.2.2 On Input | A | Reviewed. Theme/motion controls only change their named setting; navigation and fullscreen require deliberate activation. |
| 3.2.3 Consistent Navigation | AA | Reviewed. Shared header/footer maintain order on all blog routes; player navigation is consistently omitted in embedded mode where the parent supplies it. |
| 3.2.4 Consistent Identification | AA | Reviewed. Common links and controls use consistent names; dynamic action names accurately describe the next action. |
| 3.2.6 Consistent Help | A | Not applicable: no repeated human contact, self-help, or automated help mechanism. |
| 3.3.1 Error Identification | A | Not applicable: no user-submitted fields that generate validation errors; range limits are native. Load errors have a status region. |
| 3.3.2 Labels or Instructions | A | Reviewed. Motion has a native visible label and value; action buttons are explicitly named. |
| 3.3.3 Error Suggestion | AA | Not applicable: no validation-error workflow. |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA | Not applicable: no transactions, submissions, or deletion of user data. |
| 3.3.7 Redundant Entry | A | Not applicable: no multi-step data-entry process. |
| 3.3.8 Accessible Authentication (Minimum) | AA | Not applicable: no authentication. |
| 4.1.2 Name, Role, Value | A | Reviewed after canvas/label fixes. Native controls and the image role expose names/values in the browser accessibility tree. End-to-end screen-reader checks remain. |
| 4.1.3 Status Messages | AA | Reviewed after status fixes. Persistent status roles/atomic updates expose load, error, inspection, and reassembly feedback without focus changes. Spoken announcements still require screen-reader verification. |

## Remaining verification and maintenance

Before claiming broad conformance, manually exercise the published site with NVDA plus Edge/Firefox and VoiceOver plus Safari, including reading order, image descriptions, iframe entry/exit, slider announcements, live statuses, and fullscreen exit. Test actual 200%/400% browser zoom and mobile touch with a screen reader. These combinations were not available as verified test sessions in this audit; accessibility-tree inspection is not equivalent to hearing announcements in a screen reader.

Run the suite after blog UI or content changes. Check alt-text quality, foreign-language passages, new media alternatives, interaction design, and new routes manually; a generated test can detect missing markup but cannot judge whether a description conveys the intended meaning. New application features elsewhere in the monorepo require their own scope assessment, especially the future public AI editor. Keep the blog outside that editor's write authority.

The root `AGENTS.md` now directs all project work to aim for WCAG 2.2 AA and prefer shared solutions. The original blog-import manifest remains unchanged: `pnpm verify:blog-import` is historical provenance and intentionally reports these authorized modifications rather than serving as an accessibility test.

## Markdown new-tab links (2026-10-10)

`remark-attributes` enables per-link `target="_blank"`. The shared `new-tab-links.mjs` transform adds a hidden notice referenced by `aria-describedby`, including links with author-supplied accessible labels. Per the owner's preference, no notice appears in the visible link text. It adds `noopener` while preserving other rel tokens and removing an explicit `opener` token.

Four regression cases render Markdown through the blog's configured processor in Classic/Storybook and light/dark. They verify notices remain visually hidden while providing accessible descriptions, unchanged ordinary links and inline code, keyboard activation, and a null `window.opener`. The wrapped-link focus test hit-tests actual line fragments instead of empty bounding-box space. These are browser accessibility-tree checks; spoken output for the new notices has not been manually tested with a screen reader.

## Inline tooltip verification (2026-10-10)

The shared Markdown tooltip renders a native button with a dotted underline and an `aria-describedby` explanation. The native popover stays open when hovered, opens on keyboard focus or tap, and dismisses on Escape or an outside tap without moving focus. Its position is constrained to the viewport. Malformed directives preserve their source text instead of dropping article content.

Regression coverage exercises both styles (Classic and Storybook), both color modes, and 1280px/320px widths, including keyboard traversal, description exposure, tap toggling, hover persistence, dismissal, text escaping, and viewport bounds. Native top-layer popovers prevent axe from resolving overlapping backgrounds: popup contrast is checked independently against its opaque computed background, while the closed state retains the normal axe/rendered-paper contrast checks. Desktop screenshots were visually inspected in both styles. Spoken screen-reader output and physical mobile devices have not been tested for this feature.

## Contrast helper portability

The rendered-paper contrast helper masks foreground focus outlines along with text
when sampling the background. Linux font metrics exposed a focused tooltip outline
inside a text Range rectangle; treating that outline as background produced a false
1:1 ratio. A regression check verifies that outlines are excluded while actual
black text on a black background still fails. This changes the measurement only,
not the visible focus indicator. Existing keyboard and focus checks remain enabled.

## Standards used

- [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) — normative criteria and conformance requirements.
- [W3C: Label in Name](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html) — visible and accessible control names.
- [W3C: Images of Text](https://www.w3.org/WAI/WCAG22/Understanding/images-of-text.html) — using real text where presentation permits.
- [W3C: Multiple Ways](https://www.w3.org/WAI/WCAG22/Understanding/multiple-ways.html) — more than one navigation route to content.
- [W3C: Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) — narrow content-width evaluation.
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing) — automated testing and its limitations.
