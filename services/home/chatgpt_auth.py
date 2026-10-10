"""Official ChatGPT plan OAuth for a loopback-only app, never Codex credentials."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit
import uuid

import httpx
import jwt

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
DIRECT = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + DIRECT


class AuthError(ValueError):
    """Only fixed, credential-free messages may leave this boundary."""


def protect(data, decrypt=False):
    if os.name != 'nt':
        return data  # POSIX store is owner-only, below.
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise AuthError('Windows credential protection failed.')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


class CredentialStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / 'registrations.bin'
        # Prevent rotating refresh tokens from racing across server processes.
        self.lock_file = (self.directory / 'process.lock').open('a+b')
        self.lock_file.seek(0)
        self.lock_file.write(b'0')
        self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise AuthError('Another local editor is using this credential store.') from None
        if self.path.exists():
            try:
                self.data = json.loads(protect(self.path.read_bytes(), decrypt=True))
                if set(self.data) != {'host_id', 'accounts', 'active', 'welcomed'}:
                    raise ValueError()
            except Exception:
                self.close()
                raise AuthError('Cannot open the protected local registration store.') from None
        else:
            self.data = {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'accounts': {}, 'active': None, 'welcomed': False}
            self.save()

    def save(self):
        payload = protect(json.dumps(self.data).encode())
        temporary = self.directory / ('write-' + secrets.token_hex(8))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        self.lock_file.close()


class ChatGPTAuth:
    def __init__(self, directory, callback):
        self.store = CredentialStore(directory)
        self.callback = callback
        self.lock = threading.RLock()
        self.pending = None
        self.client = httpx.Client(timeout=20, follow_redirects=False, trust_env=False)
        self.jwks = jwt.PyJWKClient(JWKS, timeout=15)

    def close(self):
        self.client.close()
        self.store.close()

    def status(self):
        with self.lock:
            data = self.store.data
            active = data['accounts'].get(data['active'], {})
            return {'connected': bool(active.get('access_token')), 'active': data['active'],
                    'welcomed': data['welcomed'], 'accounts': [
                        {'id': key, 'label': account['label']} for key, account in data['accounts'].items()]}

    def begin(self, account_id=None):
        with self.lock:
            account = self.store.data['accounts'].get(account_id) if account_id else None
            if account_id and not account:
                raise AuthError('Unknown saved account.')
            transaction = {'state': secrets.token_urlsafe(32), 'nonce': secrets.token_urlsafe(32),
                           'verifier': secrets.token_urlsafe(64), 'expires': time.time() + 600,
                           'client_id': account['client_id'] if account else 'dynamic_agent_client',
                           'account_id': account_id}
            self.pending = transaction
            challenge = base64.urlsafe_b64encode(hashlib.sha256(transaction['verifier'].encode()).digest()).rstrip(b'=').decode()
            params = {'client_id': transaction['client_id'], 'redirect_uri': self.callback,
                      'response_type': 'code', 'scope': SCOPES, 'resource': RESOURCE,
                      'state': transaction['state'], 'nonce': transaction['nonce'],
                      'code_challenge': challenge, 'code_challenge_method': 'S256',
                      'ext_agent_host_id': self.store.data['host_id']}
            if account:
                if account.get('id_token'):
                    params['id_token_hint'] = account['id_token']
            else:
                params['agent_name_hint'] = 'Aether Sky Local Editor'
            return AUTHORIZE + '?' + urlencode(params)

    def token_request(self, data):
        try:
            response = self.client.post(TOKEN, data=data, headers={'Accept': 'application/json'})
            response.raise_for_status()
            if len(response.content) > 100000:
                raise ValueError()
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise AuthError('ChatGPT authorization failed. Try signing in again.') from None

    def identity(self, token, client_id, nonce=None):
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=['RS256', 'ES256'],
                                audience=client_id, issuer=ISSUER, leeway=5,
                                options={'require': ['iss', 'sub', 'aud', 'exp', 'iat']})
            if not isinstance(claims['sub'], str) or not claims['sub']:
                raise ValueError()
            if (claims.get('azp', client_id) != client_id
                    or isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != client_id):
                raise ValueError()
            if nonce is not None and claims.get('nonce') != nonce:
                raise ValueError()
            return claims
        except Exception:
            raise AuthError('ChatGPT identity could not be verified.') from None

    @staticmethod
    def credentials(tokens, previous=None):
        previous = previous or {}
        scope = tokens.get('scope', previous.get('scope', ''))
        if not isinstance(scope, str) or DIRECT not in scope.split():
            raise AuthError('ChatGPT plan permission was not granted. Sign in again.')
        if (not isinstance(tokens.get('access_token'), str) or not tokens['access_token']
                or str(tokens.get('token_type', '')).lower() != 'bearer'
                or type(tokens.get('expires_in')) not in {int, float}
                or not 0 < tokens['expires_in'] < 365 * 86400):
            raise AuthError('Invalid ChatGPT credential response.')
        refresh = tokens.get('refresh_token', previous.get('refresh_token'))
        if not isinstance(refresh, str) or not refresh:
            raise AuthError('A renewable ChatGPT session was not granted.')
        return {'access_token': tokens['access_token'], 'refresh_token': refresh,
                'id_token': tokens.get('id_token', previous.get('id_token')),
                'token_type': 'Bearer', 'scope': scope, 'expires_at': time.time() + tokens['expires_in']}

    def finish(self, params):
        with self.lock:
            transaction, self.pending = self.pending, None  # single-use, including failures
            if (not transaction or transaction['expires'] < time.time()
                    or not secrets.compare_digest(params.get('state', '').encode(), transaction['state'].encode())):
                raise AuthError('Sign-in expired or could not be verified. Start again.')
            if params.get('error'):
                raise AuthError('Sign-in was not completed. You can try again.')
            client_id = params.get('client_id', transaction['client_id'])
            if not isinstance(client_id, str) or not client_id.startswith('oaiapp_'):
                raise AuthError('Missing issued ChatGPT client registration.')
            if transaction['account_id'] and client_id != transaction['client_id']:
                raise AuthError('ChatGPT registration did not match.')
            if not params.get('code'):
                raise AuthError('Missing authorization code.')
            tokens = self.token_request({'grant_type': 'authorization_code', 'client_id': client_id,
                                         'code': params['code'], 'code_verifier': transaction['verifier'],
                                         'redirect_uri': self.callback, 'resource': RESOURCE})
            identity = self.identity(tokens.get('id_token'), client_id, transaction['nonce'])
            accounts = self.store.data['accounts']
            previous = accounts.get(transaction['account_id'])
            if previous and identity['sub'] != previous['subject']:
                raise AuthError('ChatGPT account did not match the saved registration.')
            credentials = self.credentials(tokens)
            key = hashlib.sha256((client_id + '\0' + identity['sub']).encode()).hexdigest()[:24]
            label = str(identity.get('email') or 'ChatGPT account')[:150] + ' · ' + key[:6]
            accounts[key] = {**credentials, 'client_id': client_id, 'subject': identity['sub'], 'label': label}
            self.store.data['active'] = key
            self.store.save()

    def access_token(self):
        with self.lock:
            account = self.store.data['accounts'].get(self.store.data['active'])
            if not account or not account.get('access_token'):
                raise AuthError('Connect ChatGPT in local settings first.')
            if account['expires_at'] < time.time() + 90:
                tokens = self.token_request({'grant_type': 'refresh_token', 'client_id': account['client_id'],
                                             'refresh_token': account['refresh_token'], 'resource': RESOURCE})
                if tokens.get('id_token'):
                    identity = self.identity(tokens['id_token'], account['client_id'])
                    if identity['sub'] != account['subject']:
                        raise AuthError('Refreshed ChatGPT identity did not match.')
                account.update(self.credentials(tokens, account))
                self.store.save()
            return account['access_token']

    def welcome(self):
        with self.lock:
            self.store.data['welcomed'] = True
            self.store.save()

    def sign_out(self):
        with self.lock:
            self.pending = None
            account = self.store.data['accounts'].get(self.store.data['active'])
            confirmed = True
            if account and account.get('refresh_token'):
                confirmed = False
                try:
                    configuration = self.client.get(ISSUER + '/.well-known/openid-configuration').json()
                    endpoint = configuration['revocation_endpoint']
                    parsed = urlsplit(endpoint)
                    if parsed.scheme != 'https' or parsed.netloc != 'auth.openai.com':
                        raise ValueError()
                    for delay in (0, .4, 1):
                        time.sleep(delay)
                        try:
                            response = self.client.post(endpoint, data={'token': account['refresh_token'],
                                'token_type_hint': 'refresh_token', 'client_id': account['client_id']})
                            if response.status_code == 200:
                                confirmed = True
                                break
                            if response.status_code < 500:
                                break
                        except httpx.HTTPError:
                            continue
                except (httpx.HTTPError, ValueError, KeyError):
                    pass
            if account:
                for field in ('access_token', 'refresh_token', 'id_token', 'expires_at', 'scope', 'token_type'):
                    account.pop(field, None)
            self.store.data['active'] = None
            self.store.save()
            return confirmed
