const $ = selector => document.querySelector(selector);
async function post(path, data = {}) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Home-Request': '1' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Local settings are unavailable.');
  return result;
}
function report(error) { $('#status').textContent = error.message; }
function action(selector, fn) {
  $(selector).addEventListener('click', async () => {
    $(selector).disabled = true;
    try { await fn(); } catch (error) { report(error); }
    finally { $(selector).disabled = false; }
  });
}
async function load() {
  const response = await fetch('/api/local/status');
  const status = await response.json();
  if (!response.ok) throw new Error(status.error);
  $('#controls').hidden = false;
  $('#status').textContent = status.notice || (status.connected ? 'ChatGPT is connected.' : 'Ready to connect.');
  $('#account').replaceChildren(new Option('Add a ChatGPT account', ''));
  for (const account of status.accounts) $('#account').add(new Option(account.label, account.id));
  $('#account').value = status.active || '';
  $('#signout').hidden = !status.connected;
  $('#model-settings').hidden = !status.connected;
  if (status.connected) {
    if (!status.welcomed) $('#welcome').showModal();
    const result = await post('/api/local/models');
    $('#model').replaceChildren(...result.models.map(model => new Option(model.label, model.id)));
    $('#model').value = result.model || '';
    if (!result.models.length) $('#status').textContent = 'No eligible models were returned for this account.';
  }
}
action('#signin', async () => {
  await post('/api/local/signin', { account: $('#account').value || null });
  // OAuth credentials stay on the server. This route redirects to OpenAI.
  location.assign('/auth/continue');
});
action('#signout', async () => { await post('/api/local/signout'); await load(); });
action('#got-it', async () => { await post('/api/local/welcome'); $('#welcome').close(); });
$('#model').addEventListener('change', async () => {
  try { await post('/api/local/model', { model: $('#model').value }); $('#status').textContent = 'Model selected. Open the homepage to try an edit.'; }
  catch (error) { report(error); }
});
try {
  const key = new URLSearchParams(location.hash.slice(1)).get('key');
  history.replaceState(null, '', '/local');
  if (key) await post('/api/local/unlock', { key });
  await load();
} catch (error) { report(error); }
