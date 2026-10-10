"""Load owner-authored dialogue data. No expressions, imports, or code execution.

Unknown fields, effects, and preset references fail at build/server startup.
Catalog files are private service resources, never accepted from a visitor.
"""
import random
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from frames import LAYOUTS, THEMES

CATALOG_DIR = Path(__file__).resolve().parent / 'behaviors'
MAX_EGGS = 64
REQUIRED_REPLIES = {
    'greeting', 'bio', 'capabilities', 'change_hint', 'task', 'chat', 'blocked', 'criticism', 'declined',
    'navigate_blog', 'navigate_portfolio', 'no_change',
}


class CatalogError(ValueError):
    pass


def normalize(text):
    return re.sub(r'\s+', ' ', text.casefold().replace('’', "'")).strip(' .!?').replace(',', '')


def require(condition, where, message):
    if not condition:
        raise CatalogError(f'{where}: {message}')


def fields(value, expected, where):
    require(isinstance(value, dict) and set(value) == set(expected), where,
            f'expected fields: {", ".join(sorted(expected))}')


def identifier(value, where):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,47}', value), where,
            'use an id of up to 48 lowercase letters, digits, or underscores')


def strings(value, where, minimum=1, maximum=64, length=200):
    require(isinstance(value, list) and minimum <= len(value) <= maximum, where,
            f'expected {minimum}–{maximum} strings')
    require(all(isinstance(item, str) and item.strip() and len(item) <= length
                and not any(ord(char) < 32 and char not in '\n\t' for char in item)
                for item in value), where, f'expected nonempty strings of at most {length} characters')


def phrases(value, where, minimum=1):
    strings(value, where, minimum)
    normalized = [normalize(item) for item in value]
    require(all(normalized) and len(set(normalized)) == len(normalized), where,
            'phrases must be nonempty and unique after normalization')


def words(value, where, minimum=1):
    strings(value, where, minimum)
    require(all(re.fullmatch(r'[a-z]+', item) for item in value) and len(set(value)) == len(value),
            where, 'expected unique lowercase words')


def variants(value, where):
    strings(value, where, maximum=16, length=2000)


def priority(value, where):
    require(type(value) is int and 0 <= value <= 100, where, 'priority must be an integer from 0 to 100')


def reference(value, choices, where):
    require(isinstance(value, str) and value in choices, where, 'unknown reference or preset')


def read_document(path):
    try:
        raw = path.read_bytes()
        require(len(raw) <= 131072, path, 'file exceeds 128 KiB')
        return tomllib.loads(raw.decode('utf-8'))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise CatalogError(f'{path}: {error}') from error


def version(data, expected, where):
    fields(data, {'schema_version', *expected}, where)
    require(type(data['schema_version']) is int and data['schema_version'] == 1,
            where, 'unsupported schema_version')


def validate_replies(data, where):
    version(data, {'replies'}, where)
    replies = data['replies']
    require(isinstance(replies, dict) and REQUIRED_REPLIES <= replies.keys() and len(replies) <= 128,
            where, 'missing required replies or too many replies')
    for name, reply in replies.items():
        location = f'{where}: replies.{name}'
        identifier(name, location)
        fields(reply, {'variants'}, location)
        variants(reply['variants'], location)
    return replies


def validate_flow(data, replies, where):
    version(data, {'start', 'default_prompt', 'finished_suggestion', 'accept_phrases',
                   'next_by_layout', 'steps'}, where)
    steps = data['steps']
    require(isinstance(steps, dict) and 1 <= len(steps) <= 16, where, 'expected 1–16 guided steps')
    reference(data['start'], steps, where)
    for key in ('default_prompt', 'finished_suggestion'):
        reference(data[key], replies, f'{where}: {key}')
    phrases(data['accept_phrases'], f'{where}: accept_phrases')
    fields(data['next_by_layout'], LAYOUTS, f'{where}: next_by_layout')
    for target in data['next_by_layout'].values():
        reference(target, {'none', *steps}, f'{where}: next_by_layout')
    for name, step in steps.items():
        location = f'{where}: steps.{name}'
        identifier(name, location)
        require(name != 'none', location, 'none is reserved for no pending suggestion')
        require(isinstance(step, dict), location, 'expected a step table')
        reference(step.get('effect'), {'theme', 'layout'}, location)
        common = {'effect', 'priority', 'reply', 'prompt', 'suggestion'}
        extra = {'default_theme', 'aliases', 'ask_words', 'ask_reply'} if step['effect'] == 'theme' else {'words', 'phrases', 'layout_by_current'}
        fields(step, common | extra, location)
        priority(step['priority'], location)
        for key in ('reply', 'prompt', 'suggestion'):
            reference(step[key], replies, f'{location}.{key}')
        if step['effect'] == 'theme':
            reference(step['default_theme'], THEMES, location)
            reference(step['ask_reply'], replies, location)
            words(step['ask_words'], location)
            require(isinstance(step['aliases'], dict) and bool(step['aliases']), location, 'expected theme aliases')
            for theme, aliases in step['aliases'].items():
                reference(theme, THEMES, location)
                words(aliases, location)
        else:
            words(step['words'], location, minimum=0)
            phrases(step['phrases'], location, minimum=0)
            require(step['words'] or step['phrases'], location, 'expected a word or phrase trigger')
            fields(step['layout_by_current'], LAYOUTS, location)
            for layout in step['layout_by_current'].values():
                reference(layout, LAYOUTS, location)
    return data


def egg_matches(egg, text):
    return normalize(text) in {normalize(phrase) for phrase in egg['trigger']['phrases']}


def validate_egg(data, where):
    version(data, {'id', 'priority', 'once_per', 'trigger', 'reply', 'effect', 'examples'}, where)
    identifier(data['id'], where)
    priority(data['priority'], where)
    reference(data['once_per'], {'conversation', 'unlimited'}, where)
    fields(data['trigger'], {'kind', 'phrases'}, where)
    reference(data['trigger']['kind'], {'exact_phrase'}, where)
    phrases(data['trigger']['phrases'], where)
    fields(data['reply'], {'kind', 'variants'}, where)
    reference(data['reply']['kind'], {'authored'}, where)
    variants(data['reply']['variants'], where)
    fields(data['effect'], {'kind'}, where)
    reference(data['effect']['kind'], {'none'}, where)
    fields(data['examples'], {'matches', 'does_not_match'}, where)
    for key, expected in [('matches', True), ('does_not_match', False)]:
        strings(data['examples'][key], where)
        for example in data['examples'][key]:
            require(egg_matches(data, example) == expected, where, f'contradictory {key} example: {example!r}')
    return data


@dataclass(frozen=True)
class Catalog:
    replies: dict
    flow: dict
    eggs: tuple

    def say(self, name, theme, choose=random.choice):
        # Literal substitution only. No format expressions or visitor variables.
        return choose(self.replies[name]['variants']).replace('{theme}', theme)

    @property
    def ordered_steps(self):
        return sorted(self.flow['steps'].items(), key=lambda item: (-item[1]['priority'], item[0]))

    @property
    def egg_ids(self):
        return {egg['id'] for egg in self.eggs}


def load_catalog(directory=CATALOG_DIR):
    directory = Path(directory)
    replies_path = directory / 'replies.toml'
    flow_path = directory / 'guided-edits.toml'
    replies = validate_replies(read_document(replies_path), replies_path)
    flow = validate_flow(read_document(flow_path), replies, flow_path)
    paths = sorted((directory / 'easter-eggs').glob('*.toml'))
    require(len(paths) <= MAX_EGGS, directory, f'at most {MAX_EGGS} Easter eggs are supported')
    eggs = [validate_egg(read_document(path), path) for path in paths]
    require(len({egg['id'] for egg in eggs}) == len(eggs), directory, 'duplicate Easter egg id')
    return Catalog(replies, flow, tuple(sorted(eggs, key=lambda egg: (-egg['priority'], egg['id']))))
