"""Test-only loopback server with a deliberately over-permissive fake model.

No real credentials, model requests, or application test endpoints are used.
"""
from pathlib import Path
import json
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/home'))
from server import PreviewServer
from model_client import ModelError


class HostileTestModel:
    model = 'fixture'
    available = []

    def close(self):
        pass

    def generate(self, instructions, payload, cancel, **kwargs):
        if 'current_html' not in payload:
            if 'fibonacci' in payload['request']:
                return json.dumps({'intent': 'task', 'major': False,
                    'reply': 'A Python example:\ndef fibonacci(n):\n    return matrix_power(n)[0][1]\n'
                             'Literal markup stays text: <script>window.__chatExecuted = true</script>'})
            return '{"intent":"edit","major":true,"reply":"I can try that."}'
        if 'slow' in payload['request']:
            for _ in range(60):
                time.sleep(.05)
                if cancel.is_set():
                    raise ModelError('The edit was stopped.')
        if 'hostile' in payload['request']:
            return '<main><h1>Attack</h1><script>parent.document.body.remove()</script></main>'
        return '<main style="background-color:#eadfff;color:#302040;padding:24px;"><h1>Your real edit path</h1><p>This is a test fixture through the live validator.</p></main>'


with tempfile.TemporaryDirectory() as directory:
    server = PreviewServer(('127.0.0.1', 4398), ROOT / 'apps/home/dist', live=True, auth_dir=directory)
    server.live.model.close()
    server.live.model = HostileTestModel()
    server.owner_cookie = 'test-owner-cookie'
    try:
        server.serve_forever()
    finally:
        server.server_close()
