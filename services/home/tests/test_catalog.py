import copy
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest

from catalog import CATALOG_DIR, CatalogError, load_catalog, validate_egg, validate_flow, validate_replies
from conversation import CATALOG, demo_reply, initial_state, validate_state


class CatalogTests(unittest.TestCase):
    def test_catalog_examples_route_through_the_whole_conversation(self):
        for egg in CATALOG.eggs:
            # Exercise each egg through the core router independently; separate
            # tests cover competition between eggs with overlapping phrases.
            catalog = replace(CATALOG, eggs=(egg,))
            for field, expected in [('matches', True), ('does_not_match', False)]:
                for text in egg['examples'][field]:
                    with self.subTest(egg=egg['id'], text=text):
                        reply = demo_reply(text, catalog=catalog)
                        self.assertEqual(reply.text in egg['reply']['variants'], expected)
                        self.assertEqual(egg['id'] in reply.state['seen_behaviors'],
                                         expected and egg['once_per'] == 'conversation')
                        if expected:
                            self.assertIn(reply.text, egg['reply']['variants'])
                            self.assertFalse(reply.edit)
                            self.assertIsNone(reply.action)
                            self.assertIsNone(reply.discovery)

    def test_every_authored_variant_can_be_selected(self):
        egg = CATALOG.eggs[0]
        for variant in egg['reply']['variants']:
            response = demo_reply('are you a ghost', choose=lambda options: variant)
            self.assertEqual(response.text, variant)

    def test_egg_preserves_pending_edit_and_is_once_per_conversation(self):
        pending = demo_reply('I hate your website...').state
        original = copy.deepcopy(pending)
        response = demo_reply('are you a ghost', state=pending)
        self.assertEqual(pending, original)  # The prior committed state is not mutated.
        self.assertEqual(response.state, {**pending, 'seen_behaviors': ['haunted_homepage']})
        repeated = demo_reply('is this website haunted', state=response.state)
        self.assertNotIn(repeated.text, CATALOG.eggs[0]['reply']['variants'])
        accepted = demo_reply('yes', state=repeated.state)
        self.assertEqual(accepted.state['theme'], 'lilac')
        self.assertEqual(accepted.state['layout'], 'blank')
        self.assertFalse(accepted.state['discovery_shown'])
        reset = demo_reply('', greet=True, state=accepted.state)
        self.assertEqual(reset.state, initial_state())
        self.assertIn(demo_reply('are you a ghost', state=reset.state).text,
                      CATALOG.eggs[0]['reply']['variants'])
        self.assertEqual(demo_reply('are you a ghost').state['seen_behaviors'], ['haunted_homepage'])

    def test_core_requests_and_pending_acceptance_take_precedence(self):
        for prompt in ['blog', 'github', 'bio', 'yes', 'no', 'magazine', 'add a script', 'I hate your website...']:
            egg = copy.deepcopy(CATALOG.eggs[0])
            egg['trigger']['phrases'] = [prompt]
            egg['priority'] = 100
            catalog = replace(CATALOG, eggs=(egg,))
            state = demo_reply('I hate your website...').state
            response = demo_reply(prompt, state=state, catalog=catalog)
            with self.subTest(prompt=prompt):
                self.assertNotIn(response.text, egg['reply']['variants'])
                self.assertEqual(response.state['seen_behaviors'], [])

    def test_copy_and_guided_transitions_come_from_data(self):
        flow = copy.deepcopy(CATALOG.flow)
        replies = copy.deepcopy(CATALOG.replies)
        replies['applied_color']['variants'] = ['A new {theme} reply from TOML.']
        flow['steps']['color']['default_theme'] = 'forest'
        flow['next_by_layout']['blank'] = 'studio'
        validate_flow(flow, replies, 'test flow')
        catalog = replace(CATALOG, flow=flow, replies=replies)
        proposed = demo_reply('I hate your website...', catalog=catalog)
        colored = demo_reply('yes', state=proposed.state, catalog=catalog)
        self.assertEqual(colored.state['theme'], 'forest')
        self.assertEqual(colored.state['pending'], 'studio')
        self.assertTrue(colored.text.startswith('A new forest reply from TOML.'))
        self.assertIsNone(colored.discovery)
        expanded = demo_reply('yes', state=colored.state, catalog=catalog)
        self.assertEqual(expanded.state['layout'], 'studio')
        self.assertIsNone(expanded.discovery)

    def test_startup_rejects_invalid_files_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'behaviors'
            shutil.copytree(CATALOG_DIR, root)
            load_catalog(root)
            source = root / 'easter-eggs' / 'haunted-homepage.toml'
            duplicate = root / 'easter-eggs' / 'duplicate.toml'
            duplicate.write_bytes(source.read_bytes())
            with self.assertRaisesRegex(CatalogError, 'duplicate Easter egg id'):
                load_catalog(root)
            duplicate.unlink()
            source.write_text('invalid = [', encoding='utf-8')
            with self.assertRaisesRegex(CatalogError, 'haunted-homepage.toml'):
                load_catalog(root)

    def test_unknown_fields_actions_and_contradictory_examples_are_rejected(self):
        changes = [
            ('effect', {'kind': 'javascript', 'code': 'alert(1)'}),
            ('effect', {'kind': 'navigate', 'url': 'https://evil.example'}),
            ('reply', {'kind': 'html', 'variants': ['<script>']}),
            ('reply', {'kind': 'authored', 'variants': []}),
            ('trigger', {'kind': 'regex', 'phrases': ['.*']}),
            ('trigger', {'kind': 'exact_phrase', 'phrases': ['ghost', 'Ghost?']}),
            ('examples', {'matches': ['unrelated'], 'does_not_match': ['no']}),
            ('once_per', 'cookie'), ('priority', True), ('schema_version', 2),
            ('id', '../escape'), ('extra', 'unknown'),
        ]
        for key, value in changes:
            egg = copy.deepcopy(CATALOG.eggs[0])
            egg[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(CatalogError):
                validate_egg(egg, 'test egg')

    def test_missing_reply_and_unsupported_flow_targets_are_rejected(self):
        data = {'schema_version': 1, 'replies': copy.deepcopy(CATALOG.replies)}
        del data['replies']['greeting']
        with self.assertRaises(CatalogError):
            validate_replies(data, 'test replies')
        for section, key, value in [
            ('next_by_layout', 'blank', 'not_a_step'),
            ('steps.color', 'default_theme', 'url(https://evil.example)'),
            ('steps.intro', 'reply', 'missing_reply'),
            ('steps.magazine', 'effect', 'execute'),
            ('steps.studio', 'layout_by_current', {'blank': 'script'}),
        ]:
            flow = copy.deepcopy(CATALOG.flow)
            target = flow
            for part in section.split('.'):
                target = target[part]
            target[key] = value
            with self.subTest(section=section, key=key), self.assertRaises(CatalogError):
                validate_flow(flow, CATALOG.replies, 'test flow')

    def test_priority_ties_and_unlimited_eggs_have_deterministic_routing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'behaviors'
            shutil.copytree(CATALOG_DIR, root)
            original = (root / 'easter-eggs' / 'haunted-homepage.toml').read_text(encoding='utf-8')
            for name, priority in [('aaa_ghost', 20), ('zzz_ghost', 30)]:
                text = original.replace('haunted_homepage', name).replace('priority = 20', f'priority = {priority}')
                if name == 'aaa_ghost':
                    text = text.replace('once_per = "conversation"', 'once_per = "unlimited"')
                (root / 'easter-eggs' / f'{name}.toml').write_text(text, encoding='utf-8')
            catalog = load_catalog(root)
            self.assertEqual([egg['id'] for egg in catalog.eggs], ['zzz_ghost', 'aaa_ghost', 'haunted_homepage'])
            first = demo_reply('are you a ghost', catalog=catalog)
            self.assertEqual(first.state['seen_behaviors'], ['zzz_ghost'])
            for _ in range(2):
                response = demo_reply('are you a ghost', state=first.state, catalog=catalog)
                self.assertEqual(response.state['seen_behaviors'], ['zzz_ghost'])
                self.assertEqual(response.state['pending'], 'none')

    def test_seen_state_is_bounded_and_old_tabs_are_supported(self):
        for seen in ['haunted_homepage', [None], [{}], ['unknown'], ['haunted_homepage'] * 2]:
            with self.subTest(seen=seen), self.assertRaises(ValueError):
                validate_state({**initial_state(), 'seen_behaviors': seen})
        old = initial_state()
        del old['seen_behaviors']
        self.assertEqual(validate_state(old), initial_state())


if __name__ == '__main__':
    unittest.main()
