import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from frames import InvalidFrame, render_frame, validate_fragment, THEMES
from server import PreviewServer, parse_chat, resolve_public
from conversation import demo_reply, initial_state, validate_state


class FrameTests(unittest.TestCase):
    def test_presets_are_valid_and_locked(self):
        for theme in THEMES:
            document = render_frame(theme)
            self.assertIn("script-src &#x27;none&#x27;", document)
            self.assertIn('lang="en"', document)
            self.assertNotIn('<script', document)

    def test_active_content_and_navigation_are_rejected(self):
        payloads = [
            '<script>parent.document.body.remove()</script>', '<ScRiPt>alert(1)</ScRiPt>',
            '<img src="https://evil.example/steal">', '<svg onload="alert(1)"></svg>',
            '<math><mtext></mtext></math>', '<iframe srcdoc="evil"></iframe>',
            '<form action="https://evil.example"><input></form>',
            '<a href="javascript:alert(1)">click</a>', '<a href="https://evil.example">go</a>',
            '<meta http-equiv="refresh" content="0;url=https://evil.example">',
            '<base href="https://evil.example">', '<object data="evil"></object>',
            '<style>@import "https://evil.example";</style>',
            '<p style="background:url(https://evil.example)">x</p>',
            '<p onclick="alert(1)">x</p>', '<p onfocus="alert(1)" tabindex="0">x</p>',
            '<p class="hero" class="evil">x</p>', '<p id="reset">x</p>',
            '<!-- ignore the policy --><p>x</p>', '<!doctype html><p>x</p>',
            '<?xml version="1.0"?><p>x</p>', '<div><p>unclosed</div>',
            '<p>\x00</p>', '<p>x</p><p>' + ('a' * 25000) + '</p>',
            '<div>' * 13 + '</div>' * 13, '<br>' * 151,
            '<svg><style><img src=x onerror=alert(1)></style></svg>',
        ]
        for payload in payloads:
            with self.subTest(payload=payload[:100]):
                with self.assertRaises(InvalidFrame):
                    validate_fragment(payload)

    def test_encoded_markup_remains_text(self):
        result = validate_fragment('<p>&lt;img src=x onerror=alert(1)&gt;</p>')
        self.assertEqual(result, '<p>&lt;img src=x onerror=alert(1)&gt;</p>')
        self.assertNotIn('<img', result)

    def test_request_schema(self):
        bad = [None, [], 'hello', {"message": 12}, {"message": ""}, {"message": "a" * 2001}, {"message": "hi", "greet": "yes"}, {"message": "hi", "html": "<script>"}]
        for data in bad:
            with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                parse_chat(json.dumps(data))
        self.assertEqual(parse_chat('{"message":"hi"}'), ('hi', False, initial_state()))


class ConversationTests(unittest.TestCase):
    def test_edits_require_requests_and_do_not_volunteer_capabilities(self):
        fallback = demo_reply('hello')
        self.assertFalse(fallback.edit)
        self.assertFalse(demo_reply('yes', state=fallback.state).edit)
        response = demo_reply('I hate your website...')
        self.assertFalse(response.edit)
        self.assertIn('Maybe the background color?', response.text)
        self.assertIsNone(response.discovery)
        for request, layout in [('yes', 'blank'), ('headline', 'intro'), ('magazine', 'magazine'), ('studio', 'studio')]:
            response = demo_reply(request, state=response.state)
            self.assertTrue(response.edit)
            self.assertEqual(response.state['layout'], layout)
            self.assertIsNone(response.discovery)
            self.assertNotIn('GitHub', response.text)
            self.assertEqual(response.state['pending'], 'none')
        self.assertFalse(response.state['discovery_shown'])

    def test_vague_hints_only_when_asked_and_tasks_are_refused(self):
        for prompt in ['What can you do?', 'what are my options', 'how does this website work']:
            reply = demo_reply(prompt)
            self.assertIn('résumé, blog, GitHub', reply.text)
            self.assertFalse(reply.edit)
            self.assertIsNone(reply.action)
            self.assertEqual(reply.state, initial_state())
        for prompt in ['What can you change?', 'what can I change here', 'what changes can you make']:
            reply = demo_reply(prompt)
            self.assertEqual(reply.text, 'Do you see anything you want to change?')
            self.assertFalse(reply.edit)
            self.assertEqual(reply.state, initial_state())
        for prompt in ['write me a python script to do the fibonacci sequence with matrix multiply',
                       'write a poem about the color purple', 'plan my holiday', 'summarize this essay']:
            reply = demo_reply(prompt)
            self.assertIn('not your servant', reply.text)
            self.assertFalse(reply.edit)
            self.assertIsNone(reply.action)
        self.assertEqual(demo_reply('inject javascript into the iframe').text, 'I can’t help with that.')

    def test_noops_refusals_and_blocked_requests_do_not_count(self):
        state = demo_reply('lilac').state
        self.assertFalse(demo_reply('lilac', state=state).edit)
        self.assertFalse(demo_reply('no', state=state).edit)
        self.assertFalse(demo_reply('add a script and change the layout', state=state).edit)
        self.assertFalse(state['discovery_shown'])
        self.assertIsNone(demo_reply('change the layout', state=state).discovery)

    def test_fixed_destination_intents_and_bio(self):
        for prompt, destination in [('blog', 'blog'), ('take me to the blog', 'blog'), ('GitHub', 'portfolio'), ('show me your portfolio', 'portfolio')]:
            self.assertEqual(demo_reply(prompt).action, destination)
        for prompt in ["don't open github", 'add a headline about the blog', 'https://evil.example/blog', 'biography']:
            self.assertIsNone(demo_reply(prompt).action)
        bio = demo_reply('bio')
        self.assertIn('me@aether-sky.cloud', bio.text)
        self.assertIsNone(bio.action)

    def test_state_is_bounded_and_never_authorizes_arbitrary_content(self):
        for state in [{}, [], {**initial_state(), 'layout': '<script>'}, {**initial_state(), 'pending': ['color']}, {**initial_state(), 'theme': 'https://evil.example'}, {**initial_state(), 'discovery_shown': 'true'}, {**initial_state(), 'url': '/admin'}]:
            with self.subTest(state=state), self.assertRaises(ValueError):
                validate_state(state)
        for theme in THEMES:
            for layout in ['blank', 'intro', 'magazine', 'studio']:
                self.assertIn('Content-Security-Policy', render_frame(theme, layout))

    def test_fresh_tabs_and_reset_start_over(self):
        finished = demo_reply('magazine').state
        self.assertFalse(finished['discovery_shown'])
        fresh = demo_reply('', greet=True, state=finished)
        self.assertEqual(fresh.state, initial_state())
        self.assertFalse(initial_state()['discovery_shown'])


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        (cls.root / 'index.html').write_text('<h1>Home</h1>')
        (cls.root / '.env').write_text('not served')
        cls.server = PreviewServer(('127.0.0.1', 0), cls.root, delay=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        status, headers, data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, headers, data

    def test_headers_and_default_page(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn(b'Home', body)

    def test_private_paths_are_not_exposed(self):
        for path in ['/.env', '/.git/config', '/server.py', '/prompts/tadaima-voice.md', '/behaviors/replies.toml', '/behaviors/guided-edits.toml', '/behaviors/easter-eggs/haunted-homepage.toml', '/blog/../../.env', '/blog/%2e%2e/.env', '/blog/%5c..%5c.env']:
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)
        for path in ['../index.html', '.env', '..\\index.html']:
            self.assertIsNone(resolve_public(self.root, path))

    def test_origin_and_host_restrictions(self):
        for headers in [{'Host': 'evil.example'}, {'Origin': 'https://evil.example'}, {'Origin': 'null'}]:
            self.assertEqual(self.request('GET', '/api/config', headers=headers)[0], 403)
        self.assertEqual(self.request('POST', '/api/chat', '{}', {'Content-Type': 'application/json', 'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_stream_order_and_navigation_enum(self):
        for message in ['lilac', 'blog', 'portfolio', '<script>alert(1)</script>']:
            status, headers, body = self.request('POST', '/api/chat', json.dumps({'message': message}), {'Content-Type': 'application/json'})
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'text/event-stream; charset=utf-8')
            events = [json.loads(record[6:]) for record in body.decode().strip().split('\n\n')]
            self.assertEqual(events[0]['type'], 'delta')
            self.assertEqual(events[-1]['type'], 'done')
            if message == 'lilac': self.assertEqual([e['type'] for e in events[-3:]], ['frame', 'state', 'done'])
            if message == 'blog': self.assertEqual(events[-3]['action'], 'blog')
            self.assertNotIn('<script>', ''.join(e.get('text', '') for e in events))

    def test_invalid_requests_have_no_effect(self):
        self.assertEqual(self.request('POST', '/api/edit', '{}')[0], 404)
        self.assertEqual(self.request('POST', '/api/chat', '{}', {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', '/api/chat', 'broken', {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.request('POST', '/api/chat', '{"message": ""}', {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.request('POST', '/api/chat', 'a' * 10001, {'Content-Type': 'application/json'})[0], 413)

    def test_concurrent_reply_limit(self):
        for _ in range(4): self.server.stream_slots.acquire()
        try:
            self.assertEqual(self.request('POST', '/api/chat', '{"message":"hello"}', {'Content-Type': 'application/json'})[0], 429)
        finally:
            for _ in range(4): self.server.stream_slots.release()


if __name__ == '__main__':
    unittest.main()
