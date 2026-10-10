let active = null;
let pinned = false;
let timer;

function bubble() { return active && document.getElementById(active.dataset.tooltip); }
function position() {
  const tip = bubble();
  if (!tip) return;
  const rect = active.getClientRects()[0];
  const width = tip.offsetWidth;
  const height = tip.offsetHeight;
  tip.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`;
  tip.style.top = `${Math.max(8, Math.min(rect.bottom + 8 + height <= innerHeight ? rect.bottom + 8 : rect.top - height - 8, innerHeight - height - 8))}px`;
}
function close() {
  clearTimeout(timer);
  bubble()?.hidePopover();
  active = null;
  pinned = false;
}
function open(trigger) {
  clearTimeout(timer);
  if (active === trigger) return;
  close();
  active = trigger;
  bubble()?.showPopover();
  position();
}
function maybeClose() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (active && !pinned && document.activeElement !== active && !active.matches(':hover') && !bubble()?.matches(':hover')) close();
  }, 150);
}
document.addEventListener('pointerover', event => {
  if (event.pointerType === 'touch') return;
  const trigger = event.target.closest('[data-tooltip]');
  if (trigger) open(trigger);
  if (event.target.closest('.tooltip-bubble')) clearTimeout(timer);
});
document.addEventListener('pointerout', maybeClose);
document.addEventListener('focusin', event => {
  const trigger = event.target.closest('[data-tooltip]');
  if (trigger) open(trigger);
  else close();
});
document.addEventListener('focusout', maybeClose);
document.addEventListener('click', event => {
  const trigger = event.target.closest('[data-tooltip]');
  if (!trigger) return;
  if (active === trigger && pinned) close();
  else { open(trigger); pinned = true; }
});
document.addEventListener('pointerdown', event => {
  if (!event.target.closest('[data-tooltip], .tooltip-bubble')) close();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && active) { close(); event.preventDefault(); }
});
window.addEventListener('resize', position);
document.addEventListener('scroll', position, true);
