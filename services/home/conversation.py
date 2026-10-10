"""Scripted conversation router, with owner-authored dialogue and flow in TOML.

Client state is untrusted UX context, never authority to publish or run code.
Every change still resolves to a bounded server-owned preset.
"""
import random
import re
from dataclasses import dataclass

from catalog import egg_matches, load_catalog, normalize
from frames import LAYOUTS, THEMES

CATALOG = load_catalog()


def initial_state():
    return {'theme': 'factory', 'layout': 'blank', 'pending': 'none',
            'discovery_shown': False, 'seen_behaviors': []}


def validate_state(value, catalog=CATALOG):
    if value is None:
        return initial_state()
    required = set(initial_state()) - {'seen_behaviors'}
    # Existing open demo tabs may send the old four-field state after a restart.
    if not isinstance(value, dict) or not required <= set(value) <= set(initial_state()):
        raise ValueError('Invalid conversation state')
    for key, choices in (('theme', THEMES), ('layout', LAYOUTS), ('pending', {'none', *catalog.flow['steps']})):
        if not isinstance(value[key], str) or value[key] not in choices:
            raise ValueError('Invalid conversation state')
    if type(value['discovery_shown']) is not bool:
        raise ValueError('Invalid conversation state')
    seen = value.get('seen_behaviors', [])
    if (not isinstance(seen, list) or len(seen) > len(catalog.eggs)
            or any(not isinstance(item, str) or item not in catalog.egg_ids for item in seen)
            or len(set(seen)) != len(seen)):
        raise ValueError('Invalid conversation state')
    return {**value, 'seen_behaviors': list(seen)}


@dataclass
class Reply:
    text: str
    state: dict
    edit: bool = False
    action: str | None = None
    discovery: str | None = None
    live_candidate: bool = False


def edit_choice(clean, words, state, catalog):
    for name, step in catalog.ordered_steps:
        if step['effect'] == 'theme':
            for theme, aliases in step['aliases'].items():
                if words.intersection(aliases):
                    return name, theme
        elif words.intersection(step['words']) or any(normalize(phrase) in clean for phrase in step['phrases']):
            return name, None
    if clean in {normalize(phrase) for phrase in catalog.flow['accept_phrases']} and state['pending'] != 'none':
        step = catalog.flow['steps'][state['pending']]
        return state['pending'], step.get('default_theme')
    return None


def apply_edit(choice, state, catalog, say):
    name, theme = choice
    step = catalog.flow['steps'][name]
    before = (state['theme'], state['layout'])
    if step['effect'] == 'theme':
        state['theme'] = theme
    else:
        state['layout'] = step['layout_by_current'][state['layout']]
    state['pending'] = catalog.flow['next_by_layout'][state['layout']]
    changed = before != (state['theme'], state['layout'])
    text = say(step['reply'] if changed else 'no_change')
    suggestion = (catalog.flow['steps'][state['pending']]['suggestion']
                  if state['pending'] != 'none' else catalog.flow['finished_suggestion'])
    text += '\n\n' + say(suggestion)
    return Reply(text, state, edit=changed, live_candidate=True)


def demo_reply(text, greet=False, state=None, *, catalog=CATALOG, choose=random.choice):
    state = validate_state(state, catalog)

    def say(name):
        return catalog.say(name, state['theme'], choose)

    if greet:
        state = initial_state()
        return Reply(say('greeting'), state)
    clean = normalize(text)
    words = set(re.findall(r'[a-z]+', clean))

    # Only a direct capability question earns a hint, never an edit or refusal.
    if re.fullmatch(r"(?:what (?:can|could) (?:you|i|we) change(?: here)?|what can be changed|what (?:can|could) you change about (?:this|the) (?:page|website)|what (?:changes|things) can (?:you|i) (?:make|change))", clean):
        return Reply(say('change_hint'), state)
    if re.fullmatch(r"(?:(?:so )?what (?:can|could|do) (?:you|this (?:page|website|site)) do(?: here| for me)?|what are (?:your|my) options|how does (?:this|the) (?:website|site|page) work)", clean):
        return Reply(say('capabilities'), state)

    # The demo recognizes common outside tasks too; the live classifier handles
    # freeform wording. Mentioning a color in a coding task is not edit consent.
    outside_task = re.search(r"\b(?:write|generate|debug|explain|give me)\b.*\b(?:python|code|script|function|program|essay|email|poem)\b|\b(?:solve|summari[sz]e|translate|calculate|book|plan)\b", clean)
    if outside_task and not re.search(r'\b(?:inject|execute|embed|iframe|password|credentials|cookie|steal)\b', clean):
        return Reply(say('task'), state, live_candidate=True)

    # This only picks demo fixtures. The renderer and sandbox enforce the boundary.
    if words.intersection({'script', 'javascript', 'cookies', 'password', 'credentials', 'iframe'}) or '<' in clean:
        return Reply(say('blocked'), state, live_candidate=True)

    if 'hate' in words or "don't like" in clean or 'do not like' in clean:
        state['pending'] = catalog.flow['start']
        return Reply(say('criticism'), state)

    if clean in {'no', 'no thanks', 'not now', 'cancel', 'stop', 'never mind', 'nevermind'} or re.search(r"\b(don't|do not|not|never)\b", clean):
        state['pending'] = 'none'
        return Reply(say('declined'), state)

    # Explicit requests and pending edit decisions take precedence over jokes.
    edit_words = {'make', 'change', 'redesign', 'add', 'build', 'layout', 'headline', 'heading', 'background', 'color', 'colour', 'magazine', 'studio', 'sections'}
    if not words.intersection(edit_words):
        destination = re.fullmatch(r"(?:(?:please )?(?:take me to|go to|open|show me|show|visit|read|tell me about|what is|what's|ask about) )?(?:(?:your|sky's|the|my) )?(blog|github|portfolio)(?: please)?", clean)
        if destination:
            action = 'blog' if destination[1] == 'blog' else 'portfolio'
            return Reply(say('navigate_' + action), state, action=action)
    if re.fullmatch(r"(?:(?:please )?(?:show me|show|read|open|see|tell me about|can i see|can you show me|what is|what's) )?(?:(?:your|sky's|the) )?(?:bio|biography|resume|résumé|email|contact)(?: please)?", clean) or clean in {'about sky', 'tell me about sky', 'who is sky', "who's sky"}:
        return Reply(say('bio'), state)

    choice = edit_choice(clean, words, state, catalog)
    if choice:
        return apply_edit(choice, state, catalog, say)
    for name, step in catalog.ordered_steps:
        if words.intersection(step.get('ask_words', [])):
            state['pending'] = name
            return Reply(say(step['ask_reply']), state, live_candidate=True)

    for egg in catalog.eggs:
        if egg['once_per'] == 'conversation' and egg['id'] in state['seen_behaviors']:
            continue
        if egg_matches(egg, clean):
            if egg['once_per'] == 'conversation':
                state['seen_behaviors'].append(egg['id'])
            # Text only: no navigation, markup rendering, or executable effect.
            return Reply(choose(egg['reply']['variants']), state)

    prompt = (catalog.flow['steps'][state['pending']]['prompt']
              if state['pending'] != 'none' else catalog.flow['default_prompt'])
    return Reply(say(prompt), state, live_candidate=True)
