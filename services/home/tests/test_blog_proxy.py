import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from server import PreviewServer


class BlogProxyTests(unittest.TestCase):
    def test_only_blog_gets_are_forwarded_without_owner_credentials(self):
        observed = []
        class Blog(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                observed.append((self.path, dict(self.headers)))
                body = b'watching'
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript')
                self.send_header('Set-Cookie', 'home_owner=forged')
                self.end_headers()
                self.wfile.write(body)
        upstream = ThreadingHTTPServer(('127.0.0.1', 0), Blog)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('home')
            env_module = root / 'node_modules' / 'vite' / 'env.mjs'
            home = PreviewServer(('127.0.0.1', 0), root, blog_dev_port=upstream.server_port, blog_dev_client_file=env_module)
            home_thread = threading.Thread(target=home.serve_forever, daemon=True)
            home_thread.start()
            def get(path):
                client = http.client.HTTPConnection('127.0.0.1', home.server_port)
                client.request('GET', path, headers={'Cookie': 'home_owner=secret', 'Authorization': 'Bearer secret'})
                response = client.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                client.close()
                return result
            try:
                status, headers, body = get('/@vite/client?t=123')
                self.assertEqual((status, body), (200, b'watching'))
                self.assertNotIn('Set-Cookie', headers)
                self.assertEqual(observed[0][0], '/@vite/client?t=123')
                self.assertNotIn('Cookie', observed[0][1])
                self.assertNotIn('Authorization', observed[0][1])
                self.assertEqual(get('/@fs/' + env_module.as_posix())[0], 200)
                self.assertEqual(get('/')[2], b'home')
                for path in ['/blog/.env', '/blog/../server.py', '/blog/%2e%2e/server.py',
                             '/blog/@fs/C:/secret', '/@fs/' + (root / 'private.bin').as_posix(),
                             '/blog/%5csecret', '/.local-auth/registrations.bin']:
                    self.assertEqual(get(path)[0], 404)
                self.assertEqual(len(observed), 2)
            finally:
                home.shutdown()
                home.server_close()
                home_thread.join()
                upstream.shutdown()
                upstream.server_close()
                upstream_thread.join()

    def test_proxy_failure_reports_unavailable_without_static_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            home = PreviewServer(('127.0.0.1', 0), Path(directory), blog_dev_port=1025)
            thread = threading.Thread(target=home.serve_forever, daemon=True)
            thread.start()
            try:
                from unittest.mock import patch
                with patch('server.http.client.HTTPConnection.request', side_effect=ConnectionRefusedError):
                    # Patch only the upstream connection: send the inbound request
                    # using a socket so it is unaffected by the mocked method.
                    import socket
                    with socket.create_connection(('127.0.0.1', home.server_port)) as client:
                        client.sendall(f'GET /blog/ HTTP/1.0\r\nHost: 127.0.0.1:{home.server_port}\r\n\r\n'.encode())
                        response = http.client.HTTPResponse(client)
                        response.begin()
                        self.assertEqual(response.status, 502)
                        self.assertIn(b'watcher is unavailable', response.read())
            finally:
                home.shutdown()
                home.server_close()
                thread.join()
