"""Fail-closed HTML5 fragment compiler. Never serves the model's document/head.

Only passive semantic HTML and bounded inline CSS are supported. This deliberately
small language has no URLs, active elements, stylesheets, SVG, or browser actions.
"""
import html
import math
import re

import html5lib
import tinycss2

MAX_HTML = 24000
CSP = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; media-src 'none'"
TAGS = set('main section article header footer aside div span p h1 h2 h3 h4 ul ol li dl dt dd blockquote pre code strong em b i small br hr'.split())
PROPERTIES = set('color background-color font-family font-size font-weight font-style line-height letter-spacing text-align text-decoration text-transform margin margin-top margin-bottom margin-left margin-right padding padding-top padding-bottom padding-left padding-right border border-width border-style border-color border-radius display gap row-gap column-gap grid-template-columns grid-column flex-direction flex-wrap flex-grow flex-basis align-items justify-content width max-width min-width min-height box-sizing'.split())
FUNCTIONS = {'rgb', 'rgba', 'hsl', 'hsla', 'minmax', 'repeat'}
UNITS = {'px', 'rem', 'em', 'ch', 'fr', 'vw', 'vh', 'deg'}


class RejectedHTML(ValueError):
    pass


def css_tokens(tokens, depth=0):
    if depth > 3 or len(tokens) > 80:
        raise RejectedHTML('CSS complexity limit')
    for token in tokens:
        if token.type in {'whitespace', 'hash'}:
            continue
        if token.type in {'ident', 'string'}:
            if len(token.value) > 100 or token.value.lower() in {'fixed', 'absolute', 'none', 'hidden', 'transparent'}:
                raise RejectedHTML('Unsupported CSS value')
        elif token.type in {'number', 'percentage', 'dimension'}:
            if not math.isfinite(token.value) or not 0 <= token.value <= 1200:
                raise RejectedHTML('CSS numeric limit')
            if token.type == 'dimension' and token.lower_unit not in UNITS:
                raise RejectedHTML('CSS unit')
        elif token.type == 'literal' and token.value in {',', '/'}:
            continue
        elif token.type == 'function' and token.lower_name in FUNCTIONS:
            css_tokens(token.arguments, depth + 1)
        else:
            raise RejectedHTML('Active or unsupported CSS')


def style(value):
    if len(value) > 1800:
        raise RejectedHTML('Style too large')
    declarations = tinycss2.parse_declaration_list(value, skip_whitespace=True, skip_comments=False)
    if len(declarations) > 32:
        raise RejectedHTML('Too many declarations')
    result = []
    for declaration in declarations:
        if declaration.type != 'declaration' or declaration.lower_name not in PROPERTIES or declaration.important:
            raise RejectedHTML('Unsupported CSS property')
        css_tokens(declaration.value)
        result.append(declaration.lower_name + ':' + tinycss2.serialize(declaration.value).strip() + ';')
    return ''.join(result)


def compile_fragment(source):
    if not isinstance(source, str):
        raise RejectedHTML('HTML must be text')
    try:
        size = len(source.encode('utf-8'))
    except UnicodeError:
        raise RejectedHTML('Invalid UTF-8 text') from None
    if not 0 < size <= MAX_HTML:
        raise RejectedHTML('HTML size limit')
    if any(ord(char) < 32 and char not in '\n\r\t' for char in source):
        raise RejectedHTML('Control character')
    parser = html5lib.HTMLParser(namespaceHTMLElements=False)
    root = parser.parseFragment(source)
    if parser.errors:
        raise RejectedHTML('Malformed or unsupported HTML')
    counts = {'nodes': 0, 'main': 0, 'h1': 0}

    def text(value):
        return html.escape(value or '', quote=True)

    def node(element, depth):
        counts['nodes'] += 1
        if counts['nodes'] > 160 or depth > 12:
            raise RejectedHTML('DOM complexity limit')
        tag = element.tag
        if tag not in TAGS:
            raise RejectedHTML('Unsupported HTML element')
        if tag in {'main', 'h1'}:
            counts[tag] += 1
        attributes = []
        for key, value in sorted(element.attrib.items()):
            if key == 'style':
                value = style(value)
            elif key == 'class' and re.fullmatch(r'[a-zA-Z0-9 _-]{1,100}', value):
                pass
            elif key == 'aria-label' and 0 < len(value) <= 120:
                pass
            else:
                raise RejectedHTML('Unsupported attribute')
            attributes.append(f' {key}="{text(value)}"')
        start = '<' + tag + ''.join(attributes) + '>'
        if tag in {'br', 'hr'}:
            return start + text(element.tail)
        return start + text(element.text) + ''.join(node(child, depth + 1) for child in element) + '</' + tag + '>' + text(element.tail)

    result = text(root.text) + ''.join(node(child, 1) for child in root)
    if counts['main'] != 1 or counts['h1'] != 1:
        raise RejectedHTML('Use one main and one h1')
    if len(result.encode()) > MAX_HTML:
        raise RejectedHTML('Rebuilt HTML size limit')
    return result


def validate_html(source):
    fragment = compile_fragment(source)
    if compile_fragment(fragment) != fragment:
        raise RejectedHTML('Unstable HTML round trip')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="' + html.escape(CSP, quote=True) + '">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Your homepage remix</title></head><body>' + fragment + '</body></html>')
