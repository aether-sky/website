"""Tool-less Responses streaming with hard local byte/time bounds."""
import json
import re
import time

import httpx

from chatgpt_auth import RESOURCE, AuthError


class ModelError(ValueError):
    pass


def response_format(response):
    """Bounded diagnostics: never echo provider bodies, prompts or credentials."""
    media = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    label = media if re.fullmatch(r'[a-z0-9.+-]{1,40}/[a-z0-9.+-]{1,40}', media) else 'missing or invalid Content-Type'
    return f'HTTP {response.status_code}; {label}'


class ResponsesClient:
    def __init__(self, auth):
        self.auth = auth
        self.client = httpx.Client(timeout=httpx.Timeout(15, connect=10), follow_redirects=False, trust_env=False)
        self.model = None
        self.available = []

    def close(self):
        self.client.close()

    def models(self):
        try:
            response = self.client.get(RESOURCE + '/models', headers={'Authorization': 'Bearer ' + self.auth.access_token()})
            response.raise_for_status()
            if len(response.content) > 1000000:
                raise ValueError()
            self.available = [{'id': item['slug'], 'label': item['display_name']}
                              for item in response.json()['models'] if item.get('visibility') == 'list'
                              and isinstance(item.get('slug'), str) and isinstance(item.get('display_name'), str)]
            if self.model not in {item['id'] for item in self.available}:
                self.model = self.available[0]['id'] if self.available else None
            return self.available
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ModelError('Could not load eligible ChatGPT models. Check local settings.') from None

    def generate(self, instructions, payload, cancel, *, limit=24000):
        if not self.model:
            raise ModelError('Choose an eligible model in local settings first.')
        headers = {'Authorization': 'Bearer ' + self.auth.access_token(), 'Accept': 'text/event-stream'}
        body = {'model': self.model, 'instructions': instructions, 'input': [
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
            'tools': [], 'store': False, 'stream': True}
        deadline = time.monotonic() + 90
        output, pending, total = '', '', 0
        try:
            with self.client.stream('POST', RESOURCE + '/responses', json=body, headers=headers) as response:
                if not response.is_success:
                    raise ModelError(f'ChatGPT request failed ({response_format(response)}). Check local settings.')
                media = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
                # The local-app endpoint can omit this header on valid SSE.
                # Missing metadata is allowed; completion and body checks below
                # remain mandatory. Never fall back to non-streaming JSON/HTML.
                if media and media != 'text/event-stream':
                    raise ModelError(f'ChatGPT did not return an event stream ({response_format(response)}).')
                for chunk in response.iter_text():
                    if cancel.is_set() or time.monotonic() > deadline:
                        raise ModelError('The edit was stopped or timed out.')
                    total += len(chunk.encode())
                    if total > 250000:
                        raise ModelError('Model stream exceeded its size limit.')
                    pending = (pending + chunk).replace('\r\n', '\n')
                    while '\n\n' in pending:
                        event, pending = pending.split('\n\n', 1)
                        data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
                        if not data:
                            continue
                        item = json.loads(data)
                        if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                            raise ModelError('ChatGPT returned an invalid stream event.')
                        kind = item.get('type')
                        if kind == 'response.output_text.delta':
                            if not isinstance(item.get('delta'), str):
                                raise ModelError('ChatGPT returned an invalid text delta.')
                            output += item['delta']
                            if len(output.encode()) > limit:
                                raise ModelError('Generated output exceeded its size limit.')
                        elif kind == 'response.completed':
                            completed = item.get('response')
                            if not isinstance(completed, dict) or completed.get('status') != 'completed' or not output.strip():
                                raise ModelError('Model response was not complete.')
                            return output
                        elif kind in {'response.failed', 'response.incomplete', 'error'}:
                            failed = item.get('response')
                            error = failed.get('error') if isinstance(failed, dict) else None
                            code = error.get('code') if isinstance(error, dict) else item.get('code')
                            if not isinstance(code, str):
                                code = None
                            if code in {'subscription_sharing_usage_limit_exceeded', 'subscription_sharing_usage_unavailable'}:
                                raise ModelError('ChatGPT plan usage is unavailable or at its limit. Open Manage usage in local settings.')
                            raise ModelError('ChatGPT could not complete the edit. Try again or check local settings.')
                raise ModelError('ChatGPT disconnected before completing the edit.')
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            if isinstance(error, (ModelError, AuthError)):
                raise
            raise ModelError('ChatGPT request failed. Check sign-in and model availability in local settings.') from None
