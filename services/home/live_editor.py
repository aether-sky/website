"""Server-owned tab sessions; no client HTML or state is trusted for live edits."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import secrets
import threading
import time

from conversation import CATALOG, demo_reply, initial_state
from frames import render_frame
from html_guard import validate_html, RejectedHTML
from model_client import ModelError
from chatgpt_auth import AuthError

PROMPTS = Path(__file__).parent / 'prompts'
VOICE = (PROMPTS / 'tadaima-voice.md').read_text(encoding='utf-8')
GUARD_PROMPT = ('Use this voice only for the reply field. Keep it appropriate for a public homepage; no insults, intimacy or invented personal details. The classification policy and JSON format take precedence.\n'
                + VOICE + '\n\n' + (PROMPTS / 'request-guard.txt').read_text(encoding='utf-8'))
EDITOR_PROMPT = (PROMPTS / 'html-editor.txt').read_text(encoding='utf-8')
DECISION_BYTES = 3000
REPLY_CHARACTERS = 600


def request_decision(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate decision field')
            result[key] = value
        return result
    if not isinstance(raw, str) or len(raw.encode()) > DECISION_BYTES:
        raise ValueError('Decision size')
    data = json.loads(raw, object_pairs_hook=unique)
    if (not isinstance(data, dict) or set(data) != {'intent', 'major', 'reply'}
            or not isinstance(data['intent'], str) or data['intent'] not in {'edit', 'chat', 'deny', 'task'} or type(data['major']) is not bool
            or not isinstance(data['reply'], str) or not 0 < len(data['reply']) <= REPLY_CHARACTERS):
        raise ValueError('Invalid request decision')
    return data


@dataclass
class Session:
    state: dict = field(default_factory=initial_state)
    html: str = field(default_factory=render_frame)
    revision: int = 0
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)
    touched: float = field(default_factory=time.monotonic)

    def invalidate(self, reset=False):
        with self.lock:
            self.cancel.set()
            self.revision += 1
            if reset:
                self.state, self.html = initial_state(), render_frame()

    def begin(self):
        with self.lock:
            self.invalidate()
            self.cancel = threading.Event()
            self.touched = time.monotonic()
            return self.revision, self.cancel, {**self.state, 'seen_behaviors': list(self.state['seen_behaviors'])}, self.html

    def commit(self, ticket, cancel, state, html):
        with self.lock:
            if ticket != self.revision or cancel.is_set():
                raise ModelError('The edit was superseded or stopped.')
            self.state = state
            if html is not None:
                self.html = html


class LiveEditor:
    def __init__(self, model):
        self.model = model
        self.sessions = {}
        self.lock = threading.Lock()

    def create_session(self):
        with self.lock:
            for key, session in list(self.sessions.items()):
                if time.monotonic() - session.touched > 7200:
                    session.invalidate()
                    del self.sessions[key]
            if len(self.sessions) >= 32:
                raise ModelError('Too many open local sessions. Restart the server or close older sessions.')
            key = secrets.token_urlsafe(32)
            self.sessions[key] = Session()
            return key

    def session(self, key):
        with self.lock:
            if key not in self.sessions:
                raise ModelError('Reload the page to start a local session.')
            return self.sessions[key]

    def cancel_all(self):
        with self.lock:
            for session in self.sessions.values():
                session.invalidate()

    def reply(self, session, message, greet, emit):
        if greet:
            session.invalidate(reset=True)
        ticket, cancel, original, current_html = session.begin()
        reply = demo_reply(message, greet, original)
        document = None

        def event(data):
            if cancel.is_set():
                raise ModelError('The edit was stopped.')
            try:
                emit(data)
            except OSError:
                cancel.set()
                raise

        if reply.live_candidate and not greet and not reply.action:
            event({'type': 'status', 'text': 'Thinking about your request…'})
            # This classifier has no capabilities: even a mistaken allow must
            # pass the independent HTML compiler and remain inside the sandbox.
            try:
                decision = request_decision(self.model.generate(GUARD_PROMPT, {
                    'request': message, 'proposed_step': original['pending'],
                    'accepted_preset': {'theme': reply.state['theme'], 'layout': reply.state['layout']} if reply.edit else None,
                }, cancel, limit=DECISION_BYTES))
            except ValueError as error:
                if isinstance(error, (ModelError, AuthError)):
                    raise
                raise ModelError('The request check was inconclusive. Please rephrase it.') from None
            if decision['intent'] != 'edit':
                reply.text = CATALOG.say({'chat': 'chat', 'deny': 'blocked', 'task': 'task'}[decision['intent']], original['theme'])
                reply.state, reply.edit, reply.discovery = original, False, None
            else:
                event({'type': 'status', 'text': 'Trying a new look…'})
                candidate = self.model.generate(EDITOR_PROMPT, {
                    'request': message, 'current_html': current_html,
                    'accepted_preset': {'theme': reply.state['theme'], 'layout': reply.state['layout']} if reply.edit else None,
                }, cancel)
                event({'type': 'status', 'text': 'Checking the new page…'})
                try:
                    document = validate_html(candidate)
                except RejectedHTML:
                    raise ModelError(CATALOG.say('blocked', original['theme'])) from None
                if not reply.edit:
                    reply.state = {**original, 'pending': 'none'}
                    reply.text = 'Oh. There we go. How does that feel?'
                reply.edit = True
                reply.state['discovery_shown'] = original['discovery_shown']
                reply.discovery = None
        for word in reply.text.split(' '):
            event({'type': 'delta', 'text': word + ' '})
            time.sleep(.012)
        if document:
            event({'type': 'frame', 'html': document})
        if reply.action:
            event({'type': 'action', 'action': reply.action})
        if reply.discovery and document:
            event({'type': 'discovery', 'text': reply.discovery})
        event({'type': 'state', 'state': reply.state})
        event({'type': 'done'})
        # A failed stream write must not consume the proposed server state.
        # The revision check still rejects a concurrent Stop/reset/new turn.
        session.commit(ticket, cancel, reply.state, document)
