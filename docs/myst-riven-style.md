# Storybook blog interface

The optional **Storybook** style replaces the earlier Adventure journal skin. **Classic** remains the default and can be restored using the shared Style selector. The existing `blog-style=adventure` storage value is retained so saved preferences continue working. Light/dark remains an independent preference; in the book style it changes the paper illumination while preserving the black surround.

## Screenshot references inspected

- [Myst, original Windows 16-bit linking book](https://www.mobygames.com/game/1223/myst/screenshots/win3x/6515/): an open book isolated against black, pale pages, a strongly shaded center binding, and a small linking image on the right page.
- [Riven, original Catherine journal](https://www.mystpedia.net/mystpedia/index.php?title=Fichier%3ARiven_catherine_01.jpg): a top-bound notebook with warm paper, dark leather edges, ink text, and a horizontal fold.
- [Riven, original Windows File menu](https://www.mobygames.com/game/1262/riven-the-sequel-to-myst/screenshots/windows/7751/): plain gray system menu chrome above the game viewport. It is not a brass fantasy dashboard or an inventory tray.

These references informed the actual layout, materials, and controls. No game screenshot, logo, or extracted texture is shipped. The paper grain is an original procedural SVG. Linking windows use each post’s first local Markdown illustration and share the article’s existing link and accessible name.

## Adaptation for the blog

The index is an open book: introduction on the left, published entries and linking images on the right. Articles use the journal’s horizontal binding and paper surface. Long articles remain continuous, searchable HTML; text is not rasterized or concealed behind fake page turns. Readable serif text stands in for the original handwriting. On narrow screens the book pages stack in reading order.

The shared layout owns the selector. All visual overrides live in `apps/blog/src/styles/adventure.css` and require `data-style="adventure"`. Classic retains its layout, colors, article prose, and artwork.

## Verification

The accessibility suite checks both skins in both color modes and at desktop/320px widths, plus keyboard switching, persistence, and blocked browser storage. Axe cannot calculate contrast over the textured gradients. For that specific incomplete check, `tests/accessibility/paper-contrast.mjs` samples rendered backgrounds under every text run, with glyphs temporarily transparent, and compares their luminance against the original computed text color. Other incomplete checks still fail. This supplements automated semantics and keyboard checks; it is not a claim of complete assistive-technology conformance.
