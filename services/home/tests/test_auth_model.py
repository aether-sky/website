import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt

from chatgpt_auth import ChatGPTAuth, AuthError, DIRECT, ISSUER, RESOURCE
from model_client import ResponsesClient, ModelError
from server import PreviewServer


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.auth = ChatGPTAuth(self.directory.name, 'http://127.0.0.1:8000/auth/callback')
        self.auth.jwks = Mock()
        self.auth.jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.private.public_key())

    def tearDown(self):
        self.auth.close()
        self.directory.cleanup()

    def token(self, **changes):
        claims = {'iss': ISSUER, 'aud': 'oaiapp_test', 'sub': 'subject-a', 'iat': time.time(),
                  'exp': time.time() + 3600, 'nonce': self.auth.pending['nonce'] if self.auth.pending else 'nonce'}
        claims.update(changes)
        return jwt.encode(claims, self.private, algorithm='RS256', headers={'kid': 'test'})

    def tokens(self, **changes):
        result = {'id_token': self.token(), 'access_token': 'test-access', 'refresh_token': 'test-refresh',
                  'scope': 'openid ' + DIRECT, 'token_type': 'Bearer', 'expires_in': 3600}
        result.update(changes)
        return result

    def connect(self):
        self.auth.begin()
        state = self.auth.pending['state']
        self.auth.token_request = Mock(return_value=self.tokens())
        self.auth.finish({'state': state, 'code': 'test-code', 'client_id': 'oaiapp_test'})
        return self.auth.store.data['accounts'][self.auth.store.data['active']]

    def test_pkce_freshness_scope_host_stability_and_callback(self):
        first = parse_qs(urlsplit(self.auth.begin()).query)
        second = parse_qs(urlsplit(self.auth.begin()).query)
        for key in ('state', 'nonce', 'code_challenge'):
            self.assertNotEqual(first[key], second[key])
        self.assertEqual(first['ext_agent_host_id'], second['ext_agent_host_id'])
        self.assertEqual(second['redirect_uri'], [self.auth.callback])
        self.assertEqual(second['code_challenge_method'], ['S256'])
        self.assertIn(DIRECT, second['scope'][0])
        self.assertNotIn('client_secret', second)

    def test_state_expiry_replay_denial_fail_before_exchange(self):
        for failure in ('bad-state', 'expired', 'denied', 'missing-client', 'unicode-state'):
            self.auth.begin()
            self.auth.token_request = Mock()
            params = {'state': self.auth.pending['state'], 'code': 'code', 'client_id': 'oaiapp_test'}
            if failure == 'bad-state': params['state'] = 'bad'
            if failure == 'unicode-state': params['state'] = '日本語'
            if failure == 'expired': self.auth.pending['expires'] = 0
            if failure == 'denied': params['error'] = 'access_denied'
            if failure == 'missing-client': params.pop('client_id')
            with self.subTest(failure=failure), self.assertRaises(AuthError):
                self.auth.finish(params)
            self.auth.token_request.assert_not_called()
            with self.assertRaises(AuthError): self.auth.finish(params)

    def test_real_signature_issuer_audience_expiry_nonce_and_subject_checks(self):
        self.auth.begin()
        for changes in [{'iss': 'https://evil.example'}, {'aud': 'other'}, {'exp': 0},
                        {'nonce': 'wrong'}, {'sub': ''}, {'aud': ['oaiapp_test', 'other']}, {'azp': 'other'}]:
            with self.subTest(changes=changes), self.assertRaises(AuthError):
                self.auth.identity(self.token(**changes), 'oaiapp_test', self.auth.pending['nonce'])
        bad_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tampered = jwt.encode({'iss': ISSUER}, bad_key, algorithm='RS256')
        with self.assertRaises(AuthError): self.auth.identity(tampered, 'oaiapp_test')

    def test_grant_required_and_refresh_rotation_is_saved(self):
        account = self.connect()
        self.assertEqual(self.auth.access_token(), 'test-access')
        account['expires_at'] = 0
        self.auth.token_request = Mock(return_value={'access_token': 'replacement', 'refresh_token': 'rotated',
            'expires_in': 3600, 'token_type': 'Bearer'})
        self.assertEqual(self.auth.access_token(), 'replacement')
        self.assertEqual(account['refresh_token'], 'rotated')
        self.auth.token_request.assert_called_once_with({'grant_type': 'refresh_token', 'client_id': 'oaiapp_test',
            'refresh_token': 'test-refresh', 'resource': RESOURCE})
        with self.assertRaises(AuthError):
            self.auth.credentials({'access_token': 'x', 'scope': 'openid'})

    def test_returning_signin_reuses_registration_and_checks_identity(self):
        self.connect()
        key = self.auth.store.data['active']
        params = parse_qs(urlsplit(self.auth.begin(key)).query)
        self.assertEqual(params['client_id'], ['oaiapp_test'])
        self.assertNotIn('agent_name_hint', params)
        self.assertIn('id_token_hint', params)
        self.auth.token_request = Mock(return_value=self.tokens(id_token=self.token(sub='different')))
        with self.assertRaises(AuthError):
            self.auth.finish({'state': self.auth.pending['state'], 'code': 'code'})
        self.assertEqual(self.auth.store.data['accounts'][key]['subject'], 'subject-a')

    def test_protected_storage_and_status_never_expose_tokens(self):
        self.connect()
        status = json.dumps(self.auth.status())
        self.assertNotIn('test-access', status)
        self.assertNotIn('test-refresh', status)
        if __import__('os').name == 'nt':
            self.assertNotIn(b'test-access', self.auth.store.path.read_bytes())
        host = self.auth.store.data['host_id']
        self.auth.close()
        self.auth = ChatGPTAuth(self.directory.name, self.auth.callback)
        self.assertEqual(self.auth.store.data['host_id'], host)
        self.assertEqual(self.auth.access_token(), 'test-access')

    def test_signout_clears_credentials_keeps_registration_and_reports_failure(self):
        self.connect()
        self.auth.client.close()
        self.auth.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
        self.assertFalse(self.auth.sign_out())
        self.assertFalse(self.auth.status()['connected'])
        self.assertEqual(len(self.auth.status()['accounts']), 1)
        self.assertNotIn('test-access', json.dumps(self.auth.store.data))


def stream(*events):
    return ''.join('data: ' + json.dumps(event) + '\n\n' for event in events)


class FragmentedStream(httpx.SyncByteStream):
    def __init__(self, content):
        self.content = content

    def __iter__(self):
        # Exercise CRLF and JSON split across transport chunks.
        for value in self.content:
            yield bytes([value])


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.auth = SimpleNamespace(access_token=lambda: 'unit-test-token')
        self.client = ResponsesClient(self.auth)
        self.client.model = 'model-from-catalog'

    def tearDown(self):
        self.client.close()

    def transport(self, handler):
        self.client.client.close()
        self.client.client = httpx.Client(transport=httpx.MockTransport(handler))

    def test_exact_supported_payload_and_complete_stream(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body['tools'], [])
            self.assertFalse(body['store'])
            self.assertTrue(body['stream'])
            self.assertEqual(set(body), {'model', 'instructions', 'input', 'tools', 'store', 'stream'})
            self.assertEqual(request.headers['authorization'], 'Bearer unit-test-token')
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, text=stream(
                {'type': 'response.output_text.delta', 'delta': 'hello'},
                {'type': 'response.completed', 'response': {'status': 'completed'}}))
        self.transport(handler)
        self.assertEqual(self.client.generate('policy', {'request': 'test'}, threading.Event()), 'hello')

    def test_headerless_and_parameterized_streams_require_real_completion(self):
        content = stream({'type': 'response.output_text.delta', 'delta': 'hello'},
                         {'type': 'response.completed', 'response': {'status': 'completed'}})
        for headers in [{}, {'Content-Type': 'Text/Event-Stream; charset=utf-8'}]:
            self.transport(lambda request: httpx.Response(200, headers=headers,
                stream=FragmentedStream(content.replace('\n', '\r\n').encode())))
            with self.subTest(headers=headers):
                self.assertEqual(self.client.generate('policy', {}, threading.Event()), 'hello')

    def test_missing_header_never_accepts_html_json_incomplete_or_malformed_events(self):
        cases = ['<html>A proxy error</html>', '{"status":"completed","output_text":"hello"}',
                 stream({'type': 'response.output_text.delta', 'delta': 'partial'}),
                 stream({'type': 'response.completed', 'response': None}),
                 stream({'type': 'response.output_text.delta', 'delta': []}),
                 stream({'type': 'response.failed', 'response': {'error': None}}),
                 stream({'type': 'error', 'code': []}), stream([]), stream(None),
                 'data: {invalid}\n\n']
        for content in cases:
            self.transport(lambda request: httpx.Response(200, content=content.encode()))
            with self.subTest(content=content), self.assertRaises(ModelError):
                self.client.generate('policy', {}, threading.Event())

    def test_wrong_format_and_http_errors_expose_only_bounded_metadata(self):
        for status, media in [(200, 'application/json'), (200, 'text/event-stream-fake'),
                              (401, 'application/json'), (429, 'application/json'), (503, 'text/html')]:
            self.transport(lambda request: httpx.Response(status, headers={'content-type': media},
                content=b'{"detail":"sensitive provider body"}'))
            with self.subTest(status=status, media=media), self.assertRaises(ModelError) as error:
                self.client.generate('policy', {'request': 'private prompt'}, threading.Event())
            self.assertIn(f'HTTP {status}', str(error.exception))
            self.assertIn(media, str(error.exception))
            self.assertNotIn('sensitive provider body', str(error.exception))
            self.assertNotIn('private prompt', str(error.exception))
            self.assertNotIn('unit-test-token', str(error.exception))

    def test_disconnect_failure_incomplete_size_and_cancel_fail_closed(self):
        cases = [('', False, 100),
            (stream({'type': 'response.output_text.delta', 'delta': 'partial'}), False, 100),
            (stream({'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_limit_exceeded'}}}), False, 100),
            (stream({'type': 'response.incomplete'}), False, 100),
            (stream({'type': 'response.output_text.delta', 'delta': 'too long'}), False, 2),
            (stream({'type': 'response.output_text.delta', 'delta': 'hello'}), True, 100)]
        for content, cancelled, limit in cases:
            self.transport(lambda request: httpx.Response(200, headers={'content-type': 'text/event-stream'}, text=content))
            event = threading.Event()
            if cancelled: event.set()
            with self.subTest(content=content), self.assertRaises(ModelError):
                self.client.generate('policy', {}, event, limit=limit)

    def test_model_catalog_is_filtered_and_order_preserved(self):
        self.transport(lambda request: httpx.Response(200, json={'models': [
            {'slug': 'hidden', 'display_name': 'Hidden', 'visibility': 'hide'},
            {'slug': 'first', 'display_name': 'First', 'visibility': 'list'},
            {'slug': 'second', 'display_name': 'Second', 'visibility': 'list'}]}))
        self.assertEqual([item['id'] for item in self.client.models()], ['first', 'second'])
        self.assertEqual(self.client.model, 'first')


class LocalTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.server = PreviewServer(('127.0.0.1', 0), cls.root, delay=0, live=True, auth_dir=cls.root / 'auth')
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def request(self, method, path, body=None, owner=False, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        base = {'Content-Type': 'application/json', 'X-Home-Request': '1'}
        if owner: base['Cookie'] = 'home_owner=' + self.server.owner_cookie
        connection.request(method, path, body=json.dumps(body) if body is not None else None, headers={**base, **(headers or {})})
        response = connection.getresponse()
        status, payload = response.status, response.read()
        connection.close()
        return status, payload

    def test_owner_bootstrap_and_non_owner_cannot_spend_plan(self):
        self.assertEqual(self.request('GET', '/api/local/status')[0], 403)
        self.assertEqual(self.request('POST', '/api/local/signin', {})[0], 403)
        status, body = self.request('GET', '/api/config')
        self.assertEqual(json.loads(body)['mode'], 'demo')
        key = self.server.unlock_key
        self.assertEqual(self.request('POST', '/api/local/unlock', {'key': key})[0], 200)
        self.assertEqual(self.request('POST', '/api/local/unlock', {'key': key})[0], 403)

    def test_cross_origin_missing_custom_header_and_unknown_session_rejected(self):
        for headers in [{'Origin': 'https://evil.example'}, {'Origin': 'null'}, {'Host': 'attacker.example'}, {'X-Home-Request': ''}]:
            self.assertEqual(self.request('POST', '/api/local/signin', {}, owner=True, headers=headers)[0], 403)
        self.assertEqual(self.request('POST', '/api/reset', {}, owner=True, headers={'X-Home-Session': 'bad'})[0], 400)

    def test_live_ignores_forged_state_and_cannot_supply_html(self):
        status, config = self.request('GET', '/api/config', owner=True)
        session = json.loads(config)['session']
        self.assertEqual(self.request('POST', '/api/chat', {'message': 'yes', 'html': '<script>x</script>'}, owner=True,
                                      headers={'X-Home-Session': session})[0], 400)
        status, body = self.request('POST', '/api/chat', {'message': 'bio'}, owner=True, headers={'X-Home-Session': session})
        self.assertEqual(status, 200)
        self.assertIn(b'me@aether-sky.cloud', body)
        self.assertNotIn(b'access_token', body)
        self.assertEqual(self.request('POST', '/api/reset', {}, owner=True, headers={'X-Home-Session': session})[0], 200)

    def test_no_auth_files_are_served(self):
        for path in ['/.local-auth/registrations.bin', '/auth/registrations.bin', '/requirements.txt', '/html_guard.py']:
            self.assertIn(self.request('GET', path)[0], {403, 404})
