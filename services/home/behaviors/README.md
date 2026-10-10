# Authoring homepage dialogue

The Python service reads these UTF-8 TOML files once at startup. No dependency
installation is needed; parsing uses Python's standard-library `tomllib`.
The demo and local LLM editor share these authored replies. In live mode the
model classifies requests; its freeform non-edit prose is not shown.

| File | What to edit |
| --- | --- |
| [replies.toml](replies.toml) | Greeting, bio, refusals, navigation replies, edit acknowledgments, and suggestions |
| [guided-edits.toml](guided-edits.toml) | Accepted phrases, edit triggers, default color, layout transitions, and the next suggestion |
| [easter-eggs/haunted-homepage.toml](easter-eggs/haunted-homepage.toml) | Example of an optional, once-per-conversation joke |

## Add an Easter egg

1. Copy `easter-eggs/haunted-homepage.toml` to another `.toml` file in that directory.
2. Give it a unique `id`: up to 48 lowercase letters, digits, and underscores,
   starting with a letter. Keep the ID stable when changing dialogue.
3. Change `trigger.phrases` and `reply.variants`. A matching reply randomly selects
   one variant; it is streamed as plain text. Use one variant for exact wording.
4. Update both `examples.matches` and `examples.does_not_match`. Include examples
   that should *not* activate the joke, especially incidental mentions or quotes.
5. Run the checks below, restart the Python preview, and refresh the page.

For the supplied example, ask **“Is this website haunted?”** or **“Are you a ghost?”**.
The reply does not change the frame or clear a pending edit. After it fires once,
repeating either phrase resumes the ordinary conversation. Reset makes the egg
available again. `once_per = "unlimited"` allows a reply on every match instead.

`exact_phrase` matches the entire message after case folding, whitespace collapse,
curly-apostrophe normalization, trimming outer spaces/`.!?`, and removing commas.
It does not match quoted phrases or phrases embedded in a longer sentence.
There are no configurable regexes or semantic/LLM triggers yet.

Higher `priority` wins among eligible eggs, from 0 to 100; ties use alphabetical
ID order. An already-seen once-only egg is skipped, allowing another eligible egg
to match. Core requests always come first: demo refusals, criticism, declining,
requested navigation/bio, explicit edits, and acceptance of a pending edit.
Priority cannot override those routes. Avoid giving eggs phrases such as “yes”
or “blog”; the example tests catch these collisions with the core router.

Schema version 1 supports `reply.kind = "authored"` and `effect.kind = "none"`
for eggs. Unknown fields/kinds are rejected. New effect types need explicit
Python support and tests; TOML cannot introduce scripts, raw HTML, arbitrary
URLs, or executable expressions. The files are not served by the public API.

## Change the guided conversation

In `replies.toml`, each `[replies.ID]` has a `variants` array. TOML triple-quoted
strings support paragraphs. In core replies, `{theme}` is replaced with the
validated preset name; no other interpolation or expression evaluation occurs.
Keep the required reply IDs. New reply IDs can be referenced by guided steps.

`guided-edits.toml` defines these controls:

- `start`: the pending suggestion after the initial criticism.
- `accept_phrases`: whole-message phrases that accept the pending suggestion.
- `default_prompt` and `finished_suggestion`: reply IDs used outside a pending step.
- `next_by_layout`: the next step after an accepted edit, selected using the actual
  resulting layout. `none` ends the sequence. This also handles direct requests
  that skip ahead or change a color in an already expanded layout.
- Each step's `reply`, `prompt`, and `suggestion`: reply IDs for an applied edit,
  a reminder when the input is unclear, and an invitation to this step.
- A `theme` step's `aliases`, `default_theme`, `ask_words`, and `ask_reply`: named
  color selection, the color for “yes,” and a question when no color was specified.
- A `layout` step's `words`, `phrases`, and `layout_by_current`: whole-word or
  contained-phrase triggers and the resulting layout for each existing layout.
  Higher step `priority` wins when multiple edit triggers match; ties use step ID.

Only renderer-owned theme/layout names are accepted. The current presets are
`factory`, `lilac`, `forest`, `sunset` and `blank`, `intro`, `magazine`, `studio`.
An authored suggestion changes nothing until accepted or explicitly requested.
The current `next_by_layout` values are all `none`, so visitors choose subsequent
edits themselves. No edit triggers a capability announcement. Only direct questions
such as "what can you do?" reveal `capabilities`; "what can you change?" uses
`change_hint`. `task` is the unrelated-work refusal and `blocked` is the brief
safety refusal. These routes take precedence over Easter eggs.

## Validate and preview

Run from the repository root (Python 3.12+):

```sh
pnpm exec turbo run build test --filter=@website/home-service
pnpm test:home:ui
pnpm dev:home
```

Stop an existing `dev:home` process before restarting it. TOML edits require a
restart; they are not hot-reloaded. Files resolve relative to the service module,
so the working directory does not affect catalog loading.

Build and startup reject malformed TOML, unknown fields, missing reply/step
references, unsupported presets/effects, contradictory matcher examples, and
duplicate egg IDs. Service tests run every egg's positive/negative examples
through the core router independently and verify precedence, repetition, reset,
and state bounds. Browser tests exercise streaming and uncommitted replies.

There may be up to 64 eggs, 16 guided steps, and 128 named replies. Each reply has
1–16 variants of up to 2,000 characters; each file is at most 128 KiB. These limits
keep the catalog and request state bounded. Seen IDs are demo UX state in the
visitor's tab. They commit only after the full stream completes; stopping or
interrupting a reply does not consume an egg. They do not grant permissions or
provide authoritative production session state.
