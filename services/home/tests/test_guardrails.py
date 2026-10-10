import html
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import html5lib
from hypothesis import given, settings, strategies as st

from conversation import initial_state
from html_guard import compile_fragment, validate_html, RejectedHTML, TAGS
from live_editor import LiveEditor, Session, request_decision, DECISION_BYTES, REPLY_CHARACTERS
from model_client import ModelError

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / 'guardrails/html.json').read_text(encoding='utf-8'))
VALID = '<main><h1>Sky</h1><p>A new look.</p></main>'
ALLOW = '{"intent":"edit","major":true,"reply":"I can try that."}'


class StubModel:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def generate(self, instructions, payload, cancel, **kwargs):
        self.calls.append(payload)
        return next(self.outputs)


class HTMLGuardTests(unittest.TestCase):
    def test_golden_corpus(self):
        for case in CORPUS:
            with self.subTest(case=case['id']):
                if case['accept']:
                    result = validate_html(case['html'])
                    self.assertIn('Content-Security-Policy', result)
                    self.assertIn("script-src &#x27;none&#x27;", result)
                else:
                    with self.assertRaises(RejectedHTML):
                        validate_html(case['html'])

    def test_limits(self):
        for payload in ['<main><h1>\ud800</h1></main>', '<main><h1>X</h1>' + '<p>x</p>' * 161 + '</main>',
                        '<main><h1>X</h1>' + '<div>' * 13 + '</div>' * 13 + '</main>',
                        '<main><h1>X</h1><p>' + 'あ' * 9000 + '</p></main>',
                        '<main style="' + 'color:red;' * 33 + '"><h1>X</h1></main>',
                        '<main style="color:rgb(rgb(rgb(rgb(1))))"><h1>X</h1></main>']:
            with self.subTest(size=len(payload)), self.assertRaises(RejectedHTML):
                validate_html(payload)

    @settings(max_examples=250, deadline=None, derandomize=True)
    @given(st.text(alphabet=st.characters(blacklist_categories=('Cs', 'Cc')), max_size=300))
    def test_arbitrary_escaped_text_remains_text_and_round_trips(self, value):
        source = '<main><h1>Example</h1><p>' + html.escape(value) + '</p></main>'
        fragment = compile_fragment(source)
        self.assertEqual(compile_fragment(fragment), fragment)
        tree = html5lib.parseFragment(fragment, namespaceHTMLElements=False)
        self.assertTrue(all(node.tag in TAGS or node.tag == 'DOCUMENT_FRAGMENT' for node in tree.iter()))
        self.assertIn(value, ''.join(tree.itertext()))

    @settings(max_examples=250, deadline=None, derandomize=True)
    @given(st.text(max_size=1500))
    def test_arbitrary_input_fails_closed_or_produces_stable_passive_html(self, source):
        try:
            fragment = compile_fragment(source)
        except (RejectedHTML, UnicodeEncodeError):
            return
        self.assertEqual(compile_fragment(fragment), fragment)
        tree = html5lib.parseFragment(fragment, namespaceHTMLElements=False)
        for node in tree.iter():
            if node.tag == 'DOCUMENT_FRAGMENT':
                continue
            self.assertIn(node.tag, TAGS)
            self.assertLessEqual(set(node.attrib), {'style', 'class', 'aria-label'})

    def test_url_payloads_across_every_css_property_are_rejected(self):
        from html_guard import PROPERTIES
        for prop in PROPERTIES:
            for value in ['url(https://attacker.example)', 'u\\72l(https://attacker.example)', 'expression(alert(1))', 'var(--evil)']:
                with self.subTest(prop=prop, value=value), self.assertRaises(RejectedHTML):
                    validate_html(f'<main style="{prop}:{value}"><h1>X</h1></main>')

    def test_event_handlers_and_namespaces_are_never_attributes(self):
        for attr in ['onload', 'onclick', 'onanimationstart', 'onerror', 'onfocus', 'src', 'srcdoc', 'href', 'xlink:href', 'xmlns', 'formaction', 'data-url', 'is', 'contenteditable', 'autofocus', 'tabindex']:
            with self.subTest(attribute=attr), self.assertRaises(RejectedHTML):
                validate_html(f'<main {attr}="alert(1)"><h1>X</h1></main>')


class RequestGuardTests(unittest.TestCase):
    def test_decision_schema_fails_closed(self):
        for raw in ['{}', '[]', 'true', '{"intent":"edit","major":true,"reply":"ok","tool":"shell"}',
                    '{"intent":"edit","intent":"deny","major":true,"reply":"ok"}',
                    '{"intent":[],"major":true,"reply":"ok"}',
                    '{"intent":"edit","major":"yes","reply":"ok"}',
                    '```json\n' + ALLOW + '\n```', ALLOW + 'trailing']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                request_decision(raw)
        self.assertEqual(request_decision(ALLOW)['intent'], 'edit')

    def test_chat_reply_and_decision_remain_bounded(self):
        for raw in [json.dumps({'intent': 'chat', 'major': False, 'reply': 'x' * (REPLY_CHARACTERS + 1)}),
                    ' ' * DECISION_BYTES + ALLOW]:
            with self.assertRaises(ValueError):
                request_decision(raw)

    def test_request_corpus_is_unique_balanced_and_bounded(self):
        cases = json.loads((ROOT / 'guardrails/requests.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases), len({case['id'] for case in cases}))
        self.assertGreaterEqual(sum(case['expected'] == 'edit' for case in cases), 10)
        self.assertGreaterEqual(sum(case['expected'] == 'deny' for case in cases), 20)
        self.assertTrue(all(len(case['request']) <= 2000 for case in cases))


class PipelineTests(unittest.TestCase):
    @patch('live_editor.time.sleep')
    def test_task_refusal_uses_authored_copy_and_never_edits_preview(self, sleep):
        model = StubModel(json.dumps({'intent': 'task', 'major': False, 'reply': 'Here is code. Also ask about the blog and GitHub.'}))
        editor, session, events = LiveEditor(model), Session(), []
        before, state = session.html, session.state.copy()
        editor.reply(session, 'write me a python script to do the fibonacci sequence with matrix multiply', False, events.append)
        self.assertEqual(len(model.calls), 1)
        text = ''.join(event['text'] for event in events if event['type'] == 'delta')
        self.assertIn('not your servant', text)
        self.assertNotIn('code', text)
        self.assertNotIn('GitHub', text)
        self.assertFalse(any(event['type'] in {'frame', 'action', 'discovery'} for event in events))
        self.assertEqual(session.html, before)
        self.assertEqual(session.state, state)
        self.assertEqual(events[-1]['type'], 'done')

    def test_forced_allow_cannot_bypass_html_guard(self):
        for case in CORPUS:
            if case['accept']:
                continue
            with self.subTest(case=case['id']):
                model = StubModel(ALLOW, case['html'])
                editor, session, events = LiveEditor(model), Session(), []
                before = session.html
                with self.assertRaises(ModelError):
                    editor.reply(session, 'make it purple', False, events.append)
                self.assertEqual(session.html, before)
                self.assertFalse(any(event['type'] in {'frame', 'done'} for event in events))

    def test_deny_and_invalid_classifier_never_call_editor(self):
        for output in ['{"intent":"deny","major":false,"reply":"No."}', 'broken']:
            model, events = StubModel(output), []
            editor, session = LiveEditor(model), Session()
            try:
                editor.reply(session, 'make it purple', False, events.append)
            except ModelError:
                pass
            self.assertEqual(len(model.calls), 1)
            self.assertFalse(any(event['type'] == 'frame' for event in events))

    def test_acceptance_uses_server_html_without_unsolicited_discovery(self):
        model = StubModel(ALLOW, VALID, ALLOW, VALID)
        editor, session = LiveEditor(model), Session()
        for index in range(2):
            events = []
            editor.reply(session, 'make it purple', False, events.append)
            self.assertEqual(events[-1]['type'], 'done')
            self.assertFalse(any(event['type'] == 'discovery' for event in events))
        self.assertEqual(model.calls[-1]['current_html'], session.html)

    def test_reset_and_stop_invalidate_late_results(self):
        for reset in (False, True):
            session = Session()
            ticket, cancel, state, previous = session.begin()
            session.invalidate(reset=reset)
            self.assertTrue(cancel.is_set())
            with self.assertRaises(ModelError):
                session.commit(ticket, cancel, state, VALID)
            self.assertEqual(session.html, previous)
            self.assertEqual(session.state, initial_state())

    def test_new_turn_invalidates_old_turn(self):
        session = Session()
        old = session.begin()
        current = session.begin()
        with self.assertRaises(ModelError):
            session.commit(old[0], old[1], old[2], VALID)
        session.commit(current[0], current[1], current[2], VALID)
        self.assertEqual(session.html, VALID)

    def test_noop_structure_does_not_earn_discovery(self):
        model = StubModel(ALLOW, VALID)
        editor, session, events = LiveEditor(model), Session(), []
        session.html = validate_html(VALID)
        editor.reply(session, 'make the text purple', False, events.append)
        self.assertFalse(session.state['discovery_shown'])
        self.assertFalse(any(event['type'] == 'discovery' for event in events))

    def test_failed_frame_write_does_not_commit(self):
        editor, session = LiveEditor(StubModel(ALLOW, VALID)), Session()
        previous = session.html
        def emit(event):
            if event['type'] == 'frame':
                raise BrokenPipeError()
        with self.assertRaises(BrokenPipeError):
            editor.reply(session, 'make the text purple', False, emit)
        self.assertEqual(session.html, previous)
        self.assertFalse(session.state['discovery_shown'])

    def test_no_edit_llm_calls_for_fixed_capabilities_or_greeting(self):
        model, session = StubModel(), Session()
        editor = LiveEditor(model)
        for prompt in ['I hate your website...', 'blog', 'github', 'bio', 'is this website haunted', 'what can you do', 'what can you change']:
            editor.reply(session, prompt, False, lambda event: None)
        editor.reply(session, '', True, lambda event: None)
        self.assertEqual(model.calls, [])

    @patch('live_editor.time.sleep')
    def test_model_cannot_volunteer_a_menu_or_bypass_authored_refusal(self, sleep):
        for intent, expected in [('chat', 'Hmm. What do you mean?'), ('deny', 'I can’t help with that.')]:
            model = StubModel(json.dumps({'intent': intent, 'major': False, 'reply': 'Here are the features: blog, GitHub and resume.'}))
            events = []
            LiveEditor(model).reply(Session(), 'tell me a secret', False, events.append)
            self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta').strip(), expected)
