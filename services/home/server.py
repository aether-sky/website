"""Loopback homepage preview, with optional owner-only ChatGPT plan testing.

Bind only to loopback. Replace the development HTTP transport before production.
The future editor must be a separate worker with no repository/blog mounts.
"""
import argparse
import http.client
import json
import mimetypes
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

from conversation import demo_reply, validate_state
from frames import render_frame

PORTFOLIO_URL = "https://github.com/aether-sky"
EMAIL = "me@aether-sky.cloud"
BLOG_DEV_ASSETS = ('/@vite/', '/@id/', '/src/', '/node_modules/.vite/')
SHELL_CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; img-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"


def parse_chat(body):
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid JSON") from error
    if not isinstance(data, dict) or set(data) - {"message", "greet", "state"}:
        raise ValueError("Unsupported request")
    message = data.get("message")
    greet = data.get("greet", False)
    if not isinstance(message, str) or type(greet) is not bool or len(message) > 2000:
        raise ValueError("Message must be text, up to 2000 characters")
    if not greet and not message.strip():
        raise ValueError("Message is empty")
    return message, greet, validate_state(data.get("state"))


def resolve_public(root, relative):
    """Serve a build artifact only, never source, dotfiles, or escaped paths."""
    if not root or "\\" in relative or any(part.startswith('.') for part in relative.split('/')):
        return None
    root = Path(root).resolve()
    file = (root / relative).resolve()
    if not file.is_relative_to(root):
        return None
    if file.is_dir():
        file = (file / "index.html").resolve()
    if not file.is_relative_to(root) or not file.is_file():
        return None
    return file


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, static_dir, blog_dir=None, delay=.022, live=False, auth_dir=None, blog_dev_port=None, blog_dev_client_file=None):
        if address[0] != '127.0.0.1':
            raise ValueError('This development service must bind to IPv4 loopback.')
        super().__init__(address, Handler)
        self.static_dir = static_dir
        self.blog_dir = blog_dir
        if blog_dev_port is not None and (type(blog_dev_port) is not int or not 1024 <= blog_dev_port <= 65535 or blog_dev_port == self.server_address[1]):
            super().server_close()
            raise ValueError('Invalid blog development port')
        self.blog_dev_port = blog_dev_port
        self.blog_dev_client_file = Path(blog_dev_client_file).resolve() if blog_dev_client_file else None
        self.delay = delay
        self.stream_slots = threading.BoundedSemaphore(4)
        self.live = None
        self.auth = None
        self.owner_cookie = secrets.token_urlsafe(32)
        self.unlock_key = secrets.token_urlsafe(32)
        self.auth_lock = threading.Lock()
        self.authorization_url = None
        self.auth_notice = ''
        if live:
            from chatgpt_auth import ChatGPTAuth
            from model_client import ResponsesClient
            from live_editor import LiveEditor
            self.auth = ChatGPTAuth(auth_dir or Path(__file__).parent / '.local-auth',
                f'http://127.0.0.1:{self.server_address[1]}/auth/callback')
            self.live = LiveEditor(ResponsesClient(self.auth))

    def server_close(self):
        if self.live:
            self.live.cancel_all()
            self.live.model.close()
            self.auth.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = "HomePreview/1"

    def log_message(self, format, *args):
        # Do not log conversations or raw attacker-controlled URLs.
        pass

    def owner(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            value = cookies.get('home_owner')
            return bool(value and secrets.compare_digest(value.value.encode(), self.server.owner_cookie.encode()))
        except (CookieError, ValueError):
            return False

    def redirect(self, path):
        self.send_response(303)
        self.send_header('Location', path)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def trusted_request(self, mutation=False):
        port = self.server.server_address[1]
        authorities = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in authorities:
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{host}" for host in authorities}:
            return False
        if mutation and self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        return True

    def send_headers(self, code, content_type, length=None, blog=False, cookie=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        if not blog:
            self.send_header("Content-Security-Policy", SHELL_CSP)
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def respond(self, code, data, cookie=None):
        encoded = json.dumps(data, ensure_ascii=False).encode()
        self.send_headers(code, "application/json; charset=utf-8", len(encoded), cookie=cookie)
        self.wfile.write(encoded)

    def proxy_blog(self):
        """Development only: forward blog GETs to a fixed loopback Astro port.

        Never forward the homepage owner cookie or authorization headers.
        WebSocket HMR connects directly to Astro's loopback listener.
        """
        path = unquote(urlsplit(self.path).path)
        if '\\' in path or len(self.path) > 8192 or any(ord(char) < 32 for char in path):
            return self.respond(404, {'error': 'Not found'})
        vite_client = (path.startswith('/@fs/') and self.server.blog_dev_client_file is not None
                       and Path(path[len('/@fs/'):]).is_absolute()
                       and Path(path[len('/@fs/'):]) == self.server.blog_dev_client_file)
        ordinary_asset = (path.startswith(('/blog/', *BLOG_DEV_ASSETS))
                          and not any((part.startswith('.') and part != '.vite') or part == '@fs' for part in path.split('/')))
        if not (vite_client or ordinary_asset):
            return self.respond(404, {'error': 'Not found'})
        connection = http.client.HTTPConnection('127.0.0.1', self.server.blog_dev_port, timeout=15)
        try:
            connection.request('GET', self.path, headers={'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            body = response.read(20 * 1024 * 1024 + 1)
            if len(body) > 20 * 1024 * 1024:
                return self.respond(502, {'error': 'Blog development response too large'})
            self.send_response(response.status)
            for name in ('Content-Type', 'Location'):
                if value := response.getheader(name):
                    self.send_header(name, value)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)
        except (OSError, http.client.HTTPException):
            self.respond(502, {'error': 'The blog watcher is unavailable. Check the combined runner terminal.'})
        finally:
            connection.close()

    def do_GET(self):
        if not self.trusted_request():
            return self.respond(403, {"error": "Untrusted origin"})
        route = unquote(urlsplit(self.path).path)
        # Astro serves transformed development modules at root-relative URLs
        # even when its public pages use /blog. This exists only in watch mode.
        if self.server.blog_dev_port is not None and route.startswith((*BLOG_DEV_ASSETS, '/@fs/')):
            return self.proxy_blog()
        if route.startswith('/auth/') or route == '/api/local/status':
            if not self.server.live or not self.owner():
                return self.respond(403, {'error': 'Open the local settings link printed by the server.'})
            if route == '/auth/continue':
                with self.server.auth_lock:
                    url, self.server.authorization_url = self.server.authorization_url, None
                return self.redirect(url or '/local')
            if route == '/auth/callback':
                from chatgpt_auth import AuthError
                try:
                    query = parse_qs(urlsplit(self.path).query, max_num_fields=12)
                    if any(len(value) != 1 for value in query.values()):
                        raise ValueError()
                    self.server.live.cancel_all()
                    self.server.auth.finish({key: value[0] for key, value in query.items()})
                    self.server.live.model.model = None
                    self.server.auth_notice = 'ChatGPT connected. Choose a model below.'
                except (AuthError, ValueError) as error:
                    self.server.auth_notice = str(error) if isinstance(error, AuthError) else 'Invalid sign-in callback. Start again.'
                return self.redirect('/local')
            if route == '/api/local/status':
                return self.respond(200, {**self.server.auth.status(), 'model': self.server.live.model.model,
                                          'notice': self.server.auth_notice})
        if route == "/api/config":
            if self.server.live and self.owner():
                from model_client import ModelError
                try:
                    return self.respond(200, {'mode': 'live', 'session': self.server.live.create_session(),
                        'factory_html': render_frame(), 'portfolio_url': PORTFOLIO_URL,
                        'connected': self.server.auth.status()['connected']})
                except ModelError as error:
                    return self.respond(429, {'error': str(error)})
            return self.respond(200, {"mode": "demo", "factory_html": render_frame(), "portfolio_url": PORTFOLIO_URL})
        if route == "/health":
            return self.respond(200, {"status": "ok", "mode": "demo"})
        if route == "/blog":
            self.send_response(308)
            self.send_header("Location", "/blog/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        blog = route.startswith("/blog/")
        if blog:
            if self.server.blog_dev_port is not None:
                return self.proxy_blog()
            file = resolve_public(self.server.blog_dir, route[len('/blog/'):])
        elif route in {"/", "/index.html", "/home.css", "/home.js", "/local", "/local.js", "/local.css"}:
            name = 'index.html' if route == '/' else 'local.html' if route == '/local' else route[1:]
            file = resolve_public(self.server.static_dir, name)
        else:
            file = None
        if not file:
            return self.respond(404, {"error": "Not found. Build the site with pnpm build:site first."})
        mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".xml": "application/xml"}.get(file.suffix) or mimetypes.guess_type(file)[0] or "application/octet-stream"
        payload = file.read_bytes()
        self.send_headers(200, mime, len(payload), blog=blog)
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        if not self.trusted_request(mutation=True):
            return self.respond(403, {"error": "Untrusted origin"})
        if self.path.startswith('/api/local/') or self.path in {'/api/reset', '/api/cancel'}:
            return self.local_post()
        if self.path != "/api/chat":
            return self.respond(404, {"error": "Not found"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.respond(415, {"error": "JSON required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.headers.get("Transfer-Encoding") or not 0 < length <= 10000:
                return self.respond(413, {"error": "Request too large or unsupported encoding"})
            self.connection.settimeout(5)
            message, greet, state = parse_chat(self.rfile.read(length))
        except (ValueError, OSError):
            return self.respond(400, {"error": "Invalid chat request"})
        if not self.server.stream_slots.acquire(blocking=False):
            return self.respond(429, {"error": "Too many active replies"})
        try:
            if self.server.live and self.owner():
                from chatgpt_auth import AuthError
                from model_client import ModelError
                if self.headers.get('X-Home-Request') != '1':
                    return self.respond(403, {'error': 'Local request header required'})
                try:
                    session = self.server.live.session(self.headers.get('X-Home-Session'))
                except ModelError as error:
                    return self.respond(400, {'error': str(error)})
                self.send_headers(200, 'text/event-stream; charset=utf-8')
                try:
                    self.server.live.reply(session, message, greet, self.event)
                except (AuthError, ModelError) as error:
                    self.event({'type': 'error', 'text': str(error)})
                return
            reply = demo_reply(message, greet, state)
            document = render_frame(reply.state["theme"], reply.state["layout"]) if reply.edit else None
            self.send_headers(200, "text/event-stream; charset=utf-8")
            for word in reply.text.split(" "):
                self.event({"type": "delta", "text": word + " "})
                time.sleep(self.server.delay)
            if document:
                self.event({"type": "frame", "html": document})
            if reply.action:
                self.event({"type": "action", "action": reply.action})
            if reply.discovery:
                self.event({"type": "discovery", "text": reply.discovery})
            self.event({"type": "state", "state": reply.state})
            self.event({"type": "done"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            pass
        finally:
            self.server.stream_slots.release()

    def local_post(self):
        if not self.server.live or self.headers.get('X-Home-Request') != '1':
            return self.respond(403, {'error': 'Local mode and request header required'})
        if self.headers.get('Content-Type') != 'application/json':
            return self.respond(415, {'error': 'JSON required'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.headers.get('Transfer-Encoding') or not 0 < length <= 2000:
                raise ValueError()
            self.connection.settimeout(5)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, OSError):
            return self.respond(400, {'error': 'Invalid local request'})
        if self.path == '/api/local/unlock':
            with self.server.auth_lock:
                key = data.get('key')
                if (set(data) != {'key'} or not isinstance(key, str) or not self.server.unlock_key
                        or not secrets.compare_digest(key.encode(), self.server.unlock_key.encode())):
                    return self.respond(403, {'error': 'Use the unused settings link printed by this server.'})
                self.server.unlock_key = None
            # Loopback HTTP; HttpOnly/Lax binds the OAuth return to this browser.
            return self.respond(200, {'ok': True}, cookie='home_owner=' + self.server.owner_cookie + '; HttpOnly; SameSite=Lax; Path=/')
        if not self.owner():
            return self.respond(403, {'error': 'Local owner session required'})
        from chatgpt_auth import AuthError
        from model_client import ModelError
        try:
            if self.path in {'/api/reset', '/api/cancel'} and not data:
                self.server.live.session(self.headers.get('X-Home-Session')).invalidate(reset=self.path == '/api/reset')
                return self.respond(200, {'ok': True})
            if self.path == '/api/local/signin' and set(data) <= {'account'}:
                if data.get('account') is not None and not isinstance(data['account'], str):
                    raise ValueError()
                with self.server.auth_lock:
                    self.server.authorization_url = self.server.auth.begin(data.get('account'))
                return self.respond(200, {'ok': True})
            if self.path == '/api/local/models' and not data:
                return self.respond(200, {'models': self.server.live.model.models(), 'model': self.server.live.model.model})
            if self.path == '/api/local/model' and set(data) == {'model'}:
                if data['model'] not in {item['id'] for item in self.server.live.model.available}:
                    raise ValueError()
                self.server.live.cancel_all()
                self.server.live.model.model = data['model']
                return self.respond(200, {'ok': True})
            if self.path == '/api/local/welcome' and not data:
                self.server.auth.welcome()
                return self.respond(200, {'ok': True})
            if self.path == '/api/local/signout' and not data:
                self.server.live.cancel_all()
                confirmed = self.server.auth.sign_out()
                self.server.live.model.model = None
                self.server.live.model.available = []
                self.server.auth_notice = 'Signed out.' if confirmed else 'Signed out locally. Remote revocation was not confirmed; disconnect this app in ChatGPT settings.'
                return self.respond(200, {'ok': True, 'notice': self.server.auth_notice})
        except (AuthError, ModelError) as error:
            return self.respond(400, {'error': str(error)})
        except (TypeError, ValueError):
            return self.respond(400, {'error': 'Invalid local request'})
        return self.respond(400, {'error': 'Unknown local action or fields'})

    def event(self, data):
        self.wfile.write(("data: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode())
        self.wfile.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-dir", type=Path, required=True)
    parser.add_argument("--blog-dir", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument('--live', action='store_true', help='Enable owner-only ChatGPT sign-in and real edits on loopback')
    parser.add_argument('--blog-dev-port', type=int, help='Forward /blog/ to the loopback Astro watcher')
    parser.add_argument('--blog-dev-client-file', type=Path, help='Exact installed Vite environment module allowed for development')
    parser.add_argument('--parent-stdin', action='store_true', help='Stop when the combined runner closes stdin')
    args = parser.parse_args()
    if not (args.static_dir / "index.html").is_file():
        parser.error("Home assets missing; run pnpm build:site from the repository root.")
    server = PreviewServer(("127.0.0.1", args.port), args.static_dir, args.blog_dir, live=args.live,
                           blog_dev_port=args.blog_dev_port, blog_dev_client_file=args.blog_dev_client_file)
    print(f"Local: http://127.0.0.1:{args.port} (local development; not a production server)", flush=True)
    if args.live:
        print(f"Local settings (one use): http://127.0.0.1:{args.port}/local#key={server.unlock_key}", flush=True)
    if args.parent_stdin:
        def watch_parent():
            sys.stdin.buffer.read()
            server.shutdown()
        threading.Thread(target=watch_parent, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
