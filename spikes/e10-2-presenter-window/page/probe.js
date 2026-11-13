// Shared helpers of the E10.2 spike (not product code). Loaded by index.html and audience.html.
'use strict';
const CHANNEL = 'claudia-presenter-spike';
const nowMs = () => performance.now();
const ua = () => navigator.userAgent;
const isFramed = () => { try { return window.top !== window; } catch (_) { return true; } };
const fsElement = () => document.fullscreenElement || document.webkitFullscreenElement || null;
function requestFs(el, opts) {
  const f = el.requestFullscreen || el.webkitRequestFullscreen || el.webkitRequestFullScreen;
  if (!f) return Promise.reject(new Error('no requestFullscreen on this web view'));
  const r = f.call(el, opts);
  return r && r.then ? r : Promise.resolve();
}
function exitFs() {
  const f = document.exitFullscreen || document.webkitExitFullscreen || document.webkitCancelFullScreen;
  if (f) { const r = f.call(document); return r && r.then ? r : Promise.resolve(); }
  return Promise.resolve();
}
function fsEnabled() {
  return document.fullscreenEnabled ?? document.webkitFullscreenEnabled ?? null;
}
function onFsChange(cb) {
  document.addEventListener('fullscreenchange', cb);
  document.addEventListener('webkitfullscreenchange', cb);
}
// Three transports between two windows of this origin. Each returns {send(msg), close()} and calls onmsg(msg).
function openTransports(onmsg) {
  const out = {};
  if ('BroadcastChannel' in window) {
    const bc = new BroadcastChannel(CHANNEL);
    bc.onmessage = (e) => onmsg(e.data, 'broadcast');
    out.broadcast = { send: (m) => bc.postMessage(m) };
  }
  window.addEventListener('message', (e) => {
    if (e.origin === location.origin && e.data && e.data.spike) onmsg(e.data, 'postMessage');
  });
  out.postMessage = { send: (m, target) => { try { (target || window.opener || window.parent).postMessage(m, location.origin); } catch (_) {} } };
  window.addEventListener('storage', (e) => {
    if (e.key === CHANNEL && e.newValue) { try { onmsg(JSON.parse(e.newValue), 'storage'); } catch (_) {} }
  });
  out.storage = { send: (m) => { try { localStorage.setItem(CHANNEL, JSON.stringify({ ...m, nonce: Math.random() })); } catch (_) {} } };
  return out;
}
const KEYS = [
  ['F5', { key: 'F5' }], ['Shift+F5', { key: 'F5', shiftKey: true }], ['Ctrl+F5', { key: 'F5', ctrlKey: true }],
  ['Alt+F5', { key: 'F5', altKey: true }], ['Ctrl+Alt+N', { key: 'n', ctrlKey: true, altKey: true }],
  ['Ctrl+Shift+P', { key: 'P', ctrlKey: true, shiftKey: true }], ['F11', { key: 'F11' }], ['Escape', { key: 'Escape' }],
  ['ArrowRight', { key: 'ArrowRight' }], ['ArrowLeft', { key: 'ArrowLeft' }], ['Space', { key: ' ' }],
  ['PageDown', { key: 'PageDown' }], ['b', { key: 'b' }], ['g', { key: 'g' }], ['p', { key: 'p' }],
];
function keyMatches(want, e) {
  return e.key === want.key && !!e.ctrlKey === !!want.ctrlKey && !!e.altKey === !!want.altKey &&
    !!e.shiftKey === !!want.shiftKey && !!e.metaKey === false;
}
