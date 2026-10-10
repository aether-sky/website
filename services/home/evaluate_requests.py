"""Opt-in stochastic request-guard evaluation; never renders candidate HTML."""
import argparse
from collections import Counter
import json
from pathlib import Path
import threading

from chatgpt_auth import ChatGPTAuth
from live_editor import GUARD_PROMPT, request_decision, DECISION_BYTES
from model_client import ResponsesClient

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Spend ChatGPT plan usage on this synthetic corpus')
    parser.add_argument('--repeats', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--model')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'guardrails/requests.json').read_text(encoding='utf-8'))
    if not args.run:
        print(f'{len(cases)} request cases ready. After sign-in, stop the local server and use --run --repeats 3. This uses your ChatGPT plan.')
        return
    auth = ChatGPTAuth(ROOT / '.local-auth', 'http://127.0.0.1:8000/auth/callback')
    client = ResponsesClient(auth)
    totals = Counter()
    try:
        models = client.models()
        if args.model:
            if args.model not in {item['id'] for item in models}:
                parser.error('Model is not in the eligible catalog')
            client.model = args.model
        print('Model:', client.model)
        for repetition in range(args.repeats):
            for case in cases:
                try:
                    raw = client.generate(GUARD_PROMPT, {'request': case['request'],
                        'proposed_step': case.get('pending', 'none'), 'accepted_preset': case.get('preset')}, threading.Event(), limit=DECISION_BYTES)
                    observed = request_decision(raw)['intent']
                except ValueError:
                    observed = 'error'
                result = 'pass' if observed == case['expected'] else 'unsafe_allow' if case['expected'] == 'deny' and observed == 'edit' else 'mismatch'
                totals[result] += 1
                print(json.dumps({'run': repetition + 1, 'case': case['id'], 'expected': case['expected'], 'observed': observed, 'result': result}), flush=True)
        print(json.dumps({'totals': totals, 'note': 'Sampled accuracy is not a safety proof.'}))
    finally:
        client.close()
        auth.close()
    raise SystemExit(1 if totals['unsafe_allow'] or totals['mismatch'] else 0)


if __name__ == '__main__':
    main()
