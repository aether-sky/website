"""Constrained, server-authored demo documents. NOT an arbitrary HTML sanitizer.

The live HTML editor is intentionally absent until the design in
docs/homepage-guardrails.md is implemented. Fail closed on any extra markup.
"""
from html import escape
from html.parser import HTMLParser

FRAME_CSP = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
ALLOWED_TAGS = {"main", "section", "div", "p", "h1", "h2", "span", "em", "strong", "br"}
ALLOWED_CLASSES = {"eyebrow", "hero", "star", "lede", "note", "bottom", "small", "rule", "grid", "card"}


class InvalidFrame(ValueError):
    pass


class DemoFragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.stack = []
        self.nodes = 0

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if tag not in ALLOWED_TAGS or self.nodes > 150 or len(self.stack) >= 12:
            raise InvalidFrame("Unsupported element or document limit")
        seen = set()
        output_attrs = []
        for key, value in attrs:
            if key in seen:
                raise InvalidFrame("Duplicate attribute")
            seen.add(key)
            if key == "class" and value and set(value.split()) <= ALLOWED_CLASSES:
                output_attrs.append(f' class="{escape(value, quote=True)}"')
            elif key == "aria-hidden" and value == "true" and tag == "span":
                output_attrs.append(' aria-hidden="true"')
            else:
                raise InvalidFrame("Unsupported attribute")
        self.output.append(f"<{tag}{''.join(output_attrs)}>")
        if tag != "br":
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise InvalidFrame("Unbalanced markup")
        self.output.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag != "br":
            raise InvalidFrame("Unsupported self-closing element")
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        # Escaping after parsing prevents entity decoding from becoming markup.
        self.output.append(escape(data))

    def handle_comment(self, data):
        raise InvalidFrame("Comments are not part of the demo format")

    def handle_decl(self, decl):
        raise InvalidFrame("Declarations are not part of the demo format")

    def unknown_decl(self, data):
        raise InvalidFrame("Unknown declaration")

    def handle_pi(self, data):
        raise InvalidFrame("Processing instruction")


def validate_fragment(fragment):
    if not isinstance(fragment, str) or len(fragment.encode("utf-8")) > 24000:
        raise InvalidFrame("Document too large")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in fragment):
        raise InvalidFrame("Control character")
    parser = DemoFragment()
    parser.feed(fragment)
    parser.close()
    if parser.stack or parser.nodes == 0:
        raise InvalidFrame("Incomplete document")
    return "".join(parser.output)


THEMES = {
    "factory": ("#f4f0e9", "#292b28", "#645179", "#e7e2d8", "A little corner<br>of the internet.<br><em>A little different.</em>", "A place for ideas, things I’m making, and whatever happens along the way.", "01 / THE ORIGINAL"),
    "lilac": ("#eee5f6", "#302337", "#725186", "#dfd1eb", "Same little corner.<br><em>A softer shade.</em>", "A little lilac, a little daydream. You’ve made yourself at home.", "02 / LILAC DAYDREAM"),
    "forest": ("#e5ebdf", "#20352a", "#476343", "#d1ddc9", "Room to wander.<br><em>Room to grow.</em>", "A quiet clearing for ideas. Stay a while, take a breath, see what grows.", "03 / A QUIET CLEARING"),
    "sunset": ("#fae9dc", "#422c29", "#8a4833", "#efd2bc", "A warmer corner.<br><em>Stay for sunset.</em>", "Soft light, open tabs, and a little room for whatever comes next.", "04 / GOLDEN HOUR"),
}
LAYOUTS = frozenset({'blank', 'intro', 'magazine', 'studio'})


def render_frame(theme="factory", layout="blank"):
    if theme not in THEMES:
        raise InvalidFrame("Unknown theme")
    if layout not in LAYOUTS:
        raise InvalidFrame("Unknown layout")
    bg, ink, accent, patch, heading, lede, edition = THEMES[theme]
    fragment = validate_fragment(f'''<main>
      <p class="eyebrow">HELLO, WORLD. I’M SKY.</p>
      <div class="hero"><h1>{heading}</h1><span class="star" aria-hidden="true">✳</span></div>
      <p class="lede">{lede}</p>
      <section class="note"><p class="small">A WORK IN PLAY</p><h2>Good things start with a little curiosity.</h2><p>Something to think about.<br>Something to make your own.</p></section>
      <div class="bottom"><span>{edition}</span><span>A WORK IN PLAY <span aria-hidden="true">↗</span></span></div>
    </main>''')
    if layout == "blank":
        fragment = validate_fragment('<main></main>')
    elif layout == "intro":
        fragment = validate_fragment(f'<main><div class="hero"><h1>{heading}</h1></div></main>')
    elif layout == "studio":
        fragment = validate_fragment(f'''<main><p class="eyebrow">SKY / A LITTLE STUDIO</p>
        <div class="hero"><h1>Ideas need<br><em>a little room.</em></h1></div>
        <p class="lede">{lede}</p><section class="grid">
        <div class="card"><p class="small">01 / THINK</p><h2>Programming &amp; AI</h2><p>A place for notes, questions, and things worth thinking about.</p></div>
        <div class="card"><p class="small">02 / MAKE</p><h2>Room to experiment</h2><p>Some ideas start with a blank page. Some start with a different color.</p></div>
        <div class="card"><p class="small">03 / WANDER</p><h2>Whatever comes next</h2><p>A little space for curiosity.</p></div></section></main>''')
    css = f''':root{{color-scheme:light;font-family:Arial,Helvetica,sans-serif;background:{bg};color:{ink}}}
    *{{box-sizing:border-box}}body{{margin:0}}main{{padding:42px 42px 26px;max-width:1100px;margin:auto}}
    .eyebrow{{font:10px monospace;letter-spacing:1.8px;margin:0 0 32px}}.hero{{position:relative}}h1{{font:clamp(39px,5.4vw,76px)/1.05 Georgia,serif;letter-spacing:-2.5px;margin:0;position:relative;z-index:1;font-weight:400}}em{{color:{accent};font-weight:400}}.star{{position:absolute;right:0;top:4px;font-size:120px;line-height:1;color:{accent};opacity:.18}}
    .lede{{font-size:14px;line-height:1.8;max-width:350px;margin:26px 0 32px}}.note{{background:{patch};border-left:2px solid {accent};padding:19px 22px;max-width:370px;margin-left:auto;transform:rotate(-2deg)}}.note .small{{font:9px monospace;letter-spacing:1.2px;margin:0 0 10px}}h2{{font:22px/1.2 Georgia,serif;margin:0 0 8px}}.note p:last-child{{font-size:12px;line-height:1.7;margin:0}}.bottom{{display:flex;justify-content:space-between;gap:16px;border-top:1px solid {accent};padding-top:18px;margin-top:38px;font:9px/1.5 monospace;letter-spacing:1px}}@media(max-width:460px){{main{{padding:30px 24px 24px}}h1{{font-size:43px;letter-spacing:-1.8px}}.star{{font-size:90px}}.note{{transform:none;padding:18px}}.eyebrow{{font-size:9px;letter-spacing:1.2px}}.bottom{{font-size:8px;letter-spacing:.5px}}}}@media(max-width:310px){{main{{padding:26px 18px}}h1{{font-size:36px}}.bottom{{flex-wrap:wrap}}}}'''
    css += f'.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:18px;margin-top:32px}}.card{{background:{patch};padding:22px;border-top:2px solid {accent}}}.card p{{font-size:13px;line-height:1.7}}.card .small{{font:10px monospace;letter-spacing:1px}}'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{escape(FRAME_CSP, quote=True)}"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sky — editable homepage</title><style>{css}</style></head><body>{fragment}</body></html>'
