"""One bounded, tool-less ChatGPT request; reports transport metadata, not tokens."""
import argparse
import json
from pathlib import Path
import re
import time

from chatgpt_auth import ChatGPTAuth, RESOURCE
from model_client import ResponsesClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model')
    args = parser.parse_args()
    auth = ChatGPTAuth(Path(__file__).parent / '.local-auth', 'http://127.0.0.1:8000/auth/callback')
    client = ResponsesClient(auth)
    try:
        models = client.models()
        if args.model:
            if args.model not in {item['id'] for item in models}:
                raise ValueError('Choose a model from the signed-in account catalog.')
            client.model = args.model
        print(json.dumps({'model': client.model}), flush=True)
        request = {'model': client.model, 'input': [{'role': 'user', 'content': 'Reply with exactly OK.'}],
                   'tools': [], 'store': False, 'stream': True}
        with client.client.stream('POST', RESOURCE + '/responses', json=request,
                headers={'Authorization': 'Bearer ' + auth.access_token(), 'Accept': 'text/event-stream'}) as response:
            result = {'status': response.status_code, 'content_type': response.headers.get('content-type', 'missing'),
                      'request_id': response.headers.get('x-request-id') or response.headers.get('openai-request-id')}
            raw = b''
            deadline = time.monotonic() + 90
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline:
                    raise TimeoutError('Diagnostic exceeded 90 seconds.')
                raw += chunk
                if len(raw) > 64000:
                    raw = raw[:64000]
                    result['truncated'] = True
                    break
            result['bytes'] = len(raw)
            try:
                data = json.loads(raw)
                result['body_shape'] = type(data).__name__
                if isinstance(data, dict):
                    result['keys'] = [key for key in data if re.fullmatch(r'[a-zA-Z_]{1,60}', key)]
                    for key in ('object', 'status', 'type'):
                        value = data.get(key)
                        if isinstance(value, str) and re.fullmatch(r'[a-zA-Z_.-]{1,80}', value):
                            result['body_' + key] = value
                    error = data.get('error')
                    if isinstance(error, dict):
                        for key in ('code', 'type', 'param'):
                            value = error.get(key)
                            if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', value):
                                result['error_' + key] = value
                    result['has_detail'] = 'detail' in data
                    result['has_output'] = isinstance(data.get('output'), list)
            except ValueError:
                result['body_shape'] = 'sse' if raw.lstrip().startswith((b'data:', b'event:')) else 'other'
            print(json.dumps(result), flush=True)
    finally:
        client.close()
        auth.close()


if __name__ == '__main__':
    main()
