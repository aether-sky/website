const $ = selector => document.querySelector(selector);
const messages = $('#messages');
const frame = $('#page-frame');
const input = $('#message');
let config;
let generation = 0;
let controller;
let conversationState;

function localHeaders() {
  return { 'Content-Type': 'application/json', ...(config?.mode === 'live' ? { 'X-Home-Request': '1', 'X-Home-Session': config.session } : {}) };
}
async function invalidateLive(reset = false) {
  if (config?.mode !== 'live') return;
  const result = await fetch(reset ? '/api/reset' : '/api/cancel', { method: 'POST', headers: localHeaders(), body: '{}' });
  if (!result.ok) throw new Error('Could not stop the server session. Reload this page.');
}

function busy(active) {
  $('#send').disabled = active || !config;
  $('#stop').hidden = !active;
}

function message(role, text = '', target = messages) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const label = document.createElement('p');
  label.className = 'message-label sr-only';
  label.textContent = role === 'user' ? 'YOU' : 'TADAIMA';
  const body = document.createElement('p');
  body.className = 'message-text';
  body.textContent = text;
  article.append(label, body);
  target.append(article);
  return { article, body };
}

function showFrame(html, label) {
  // Only documents assembled and validated by our server reach this sink.
  // The sandbox is permanent; no script or same-origin permissions are granted.
  frame.srcdoc = html;
  $('#version-label').textContent = label;
}

async function* events(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let pending = '';
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      bytes += value?.byteLength || 0;
      if (bytes > 100000) throw new Error('Stream limit exceeded');
      pending += decoder.decode(value, { stream: !done });
      let boundary;
      while ((boundary = pending.indexOf('\n\n')) !== -1) {
        const record = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const data = record.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n');
        if (data) yield JSON.parse(data);
      }
      if (done) {
        if (pending.trim()) throw new Error('Incomplete event');
        break;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

async function chat(text, greet = false) {
  if (!config || controller) return;
  const current = generation;
  const abort = new AbortController();
  controller = abort;
  if (!greet) message('user', text);
  const reply = message('assistant', '', greet ? $('#initial-instructions') : messages);
  busy(true);
  $('#reply-status').classList.add('sr-only');
  $('#reply-status').textContent = 'Tadaima is replying…';
  let complete = false;
  // Changes are committed only after a complete stream, never from partial HTML.
  let nextFrame;
  let action;
  let nextState;
  let discovery;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: localHeaders(),
      body: JSON.stringify({ message: text, greet, state: conversationState }), signal: abort.signal,
    });
    if (!response.ok) throw new Error('Request failed');
    for await (const event of events(response)) {
      if (current !== generation) return;
      if (complete || !['delta', 'frame', 'action', 'state', 'discovery', 'done', 'status', 'error'].includes(event.type)) throw new Error('Invalid event sequence');
      if (event.type === 'error') { const error = new Error(event.text); error.localNotice = true; throw error; }
      if (event.type === 'status') { $('#reply-status').textContent = event.text; $('#reply-status').classList.remove('sr-only'); }
      const scroller = $('#chat-content');
      const nearBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 100;
      if (event.type === 'delta' && typeof event.text === 'string') reply.body.textContent += event.text;
      if (event.type === 'frame') nextFrame = event;
      if (event.type === 'action') action = event.action;
      if (event.type === 'state') nextState = event.state;
      if (event.type === 'discovery' && typeof event.text === 'string') discovery = event.text;
      if (event.type === 'done') complete = true;
      if (nearBottom && !greet) scroller.scrollTop = scroller.scrollHeight;
    }
    if (!complete) throw new Error('Stream interrupted');
    if (current !== generation) return;
    if (nextFrame && typeof nextFrame.html === 'string') {
      showFrame(nextFrame.html, 'Your remix');
      $('#canvas-status').textContent = 'A fresh mood, just for this visit.';
      // Reveal the invitation only after the accepted frame is committed.
      if (discovery) {
        const scroller = $('#chat-content');
        const follow = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 100;
        reply.body.textContent += '\n\n' + discovery;
        if (follow) scroller.scrollTop = scroller.scrollHeight;
      }
    }
    if (nextState) conversationState = nextState;
    $('#reply-status').textContent = 'Your turn. What are you thinking?';
    $('#reply-status').classList.add('sr-only');
    $('#announcement').textContent = reply.body.textContent;
    // Only server-selected destination enums can redirect, after a complete reply.
    // No URL in a chat message, generated HTML, or model argument is followed.
    const destination = action === 'blog' ? '/blog/' : action === 'portfolio' ? 'https://github.com/aether-sky' : null;
    if (destination) window.location.assign(destination);
  } catch (error) {
    if (current !== generation) return;
    const stopped = error.name === 'AbortError';
    const notice = stopped ? 'Reply stopped. You can keep chatting.' : error.localNotice ? error.message : 'That reply was interrupted. Please try again.';
    if (!reply.body.textContent) reply.body.textContent = notice;
    $('#reply-status').textContent = notice;
    if (!stopped) $('#reply-status').classList.remove('sr-only');
    $('#announcement').textContent = notice;
  } finally {
    if (current === generation) { controller = undefined; busy(false); }
  }
}

function send(text) {
  const trimmed = text.trim();
  if (!trimmed || controller || !config) return;
  input.value = '';
  void chat(trimmed);
}
$('#chat-form').addEventListener('submit', event => { event.preventDefault(); send(input.value); });
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(input.value); }
});
$('#stop').addEventListener('click', async () => {
  controller?.abort();
  try { await invalidateLive(); } catch (error) { $('#reply-status').textContent = error.message; $('#reply-status').classList.remove('sr-only'); }
  input.focus();
});
$('#reset').addEventListener('click', async () => {
  generation++;
  controller?.abort();
  controller = undefined;
  messages.replaceChildren();
  $('#initial-instructions').replaceChildren();
  input.value = input.defaultValue;
  conversationState = undefined;
  $('#announcement').textContent = 'Factory settings restored. Conversation cleared.';
  if (config) {
    showFrame(config.factory_html, 'Factory original');
    $('#canvas-status').textContent = 'Factory settings restored. A fresh start.';
    busy(true);
    try { await invalidateLive(true); void chat('', true); }
    catch (error) { $('#reply-status').textContent = error.message; $('#reply-status').classList.remove('sr-only'); }
  } else { void boot(); }
});

async function boot() {
  busy(true);
  try {
    const response = await fetch('/api/config', { cache: 'no-store' });
    if (!response.ok) throw new Error('Unavailable');
    config = await response.json();
    $('#plan-status').hidden = config.mode !== 'live' || !config.connected;
    showFrame(config.factory_html, 'Factory original');
    await chat('', true);
  } catch {
    $('#reply-status').textContent = 'Couldn’t connect. Use Reset to try again.';
    $('#reply-status').classList.remove('sr-only');
  } finally { if (!controller) busy(false); }
}
void boot();
