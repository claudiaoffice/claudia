'use strict';
// E10.2 spike: probes what a presenter mode can rely on in this web view. Not product code.
const $ = (id) => document.getElementById(id);
const R = { spike: 'e10-2-presenter-window', when: new Date().toISOString(), env: {}, tests: {}, keys: {}, manual: {} };
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
function row(tbl, name, verdict, note) {
  const t = $(tbl); const id = 'r-' + tbl + '-' + name.replace(/\W+/g, '_');
  let tr = document.getElementById(id);
  if (!tr) { tr = document.createElement('tr'); tr.id = id; t.appendChild(tr); }
  const cls = verdict === 'ok' ? 'ok' : verdict === 'problem' ? 'bad' : 'na';
  tr.innerHTML = `<td>${esc(name)}</td><td class="${cls}">${esc(verdict)}</td><td>${esc(note || '')}</td>`;
  R.tests[tbl + ': ' + name] = { verdict, note: note || '' };
}
const params = new URLSearchParams(location.search);
const framed = isFramed();
R.env = {
  userAgent: ua(), framed, framedAllow: params.get('framed') || null, platform: navigator.platform, lang: navigator.language,
  screen: `${screen.width}x${screen.height} avail ${screen.availWidth}x${screen.availHeight}`, dpr: devicePixelRatio,
  window: `${innerWidth}x${innerHeight}`, isExtended: typeof screen.isExtended === 'boolean' ? screen.isExtended : 'n/a',
  fullscreenEnabled: fsEnabled(), broadcastChannel: 'BroadcastChannel' in window, localStorage: (() => { try { localStorage.setItem('x', '1'); return true; } catch (_) { return false; } })(),
  windowManagementApi: 'getScreenDetails' in window, wakeLock: 'wakeLock' in navigator,
  reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
  neutralino: !!window.Neutralino, gtkHandler: !!(window.webkit && window.webkit.messageHandlers),
};
$('env').innerHTML = '<tr><th>What</th><th>Value</th></tr>' + Object.entries(R.env).map(([k, v]) => `<tr><td>${k}</td><td>${esc(v)}</td></tr>`).join('');

// --- page loads (does F5 reload?)
try { const n = Number(sessionStorage.getItem('loads') || 0) + 1; sessionStorage.setItem('loads', n); $('loads').textContent = n; R.env.pageLoads = n; }
catch (_) { $('loads').textContent = 'sessionStorage not available'; }

// --- fullscreen
onFsChange(() => { const on = !!fsElement(); $('fsbox').hidden = !on;
  row('t-fs', 'fullscreenchange fired', 'ok', `${on ? 'entered' : 'left'}; window now ${innerWidth}x${innerHeight}, screen ${screen.width}x${screen.height}`); });
$('b-fs').onclick = async () => {
  $('fsbox').hidden = false;
  const t0 = nowMs();
  try { await requestFs($('fsbox')); row('t-fs', 'requestFullscreen on an element', fsElement() ? 'ok' : 'problem', `${Math.round(nowMs() - t0)} ms; element is ${fsElement() ? 'fullscreen' : 'not fullscreen'}`); }
  catch (x) { row('t-fs', 'requestFullscreen on an element', 'problem', String(x.message || x)); }
};
$('b-fs-doc').onclick = async () => {
  try { await requestFs(document.documentElement); row('t-fs', 'requestFullscreen on the whole document', fsElement() ? 'ok' : 'problem', ''); }
  catch (x) { row('t-fs', 'requestFullscreen on the whole document', 'problem', String(x.message || x)); }
};
$('b-fs-exit').onclick = () => exitFs();

// --- second window and messaging
let audience = null, lastReady = null; const pongs = new Map(); let slide = 1; const seenVia = { broadcast: 0, postMessage: 0, storage: 0 };
const tr = openTransports((m, via) => {
  if (!m || !m.spike) return; seenVia[via]++;
  if (m.type === 'audience-ready') { lastReady = m; row('t-win', 'audience window announced itself', 'ok', `via ${via}; its window ${m.w}x${m.h}, screen ${m.sw}x${m.sh} at ${m.sx},${m.sy}; framed ${m.framed}; opener ${m.hasOpener}`); }
  if (m.type === 'pong' && pongs.has(m.id)) { pongs.get(m.id)(via); }
  if (m.type === 'audience-fullscreen') row('t-win', 'audience window fullscreen', m.on ? 'ok' : 'na', `${m.on ? 'on' : 'off'}; its window ${m.w}x${m.h}, screen ${m.sw}x${m.sh}`);
  if (m.type === 'key') { row('t-win', 'key pressed in the audience window arrived here', 'ok', m.key); if (m.key === 'ArrowRight' || m.key === ' ') $('b-next').click(); if (m.key === 'ArrowLeft') $('b-prev').click(); }
  if (m.type === 'audience-closed') row('t-win', 'audience window closed', 'na', '');
});
function sendAll(m) { for (const k of ['broadcast', 'postMessage', 'storage']) { if (tr[k]) tr[k].send(m, audience && audience.window ? audience : undefined); } }
function openAudience(features) {
  try { audience = window.open('audience.html', 'claudia-audience', features || 'popup=yes,width=960,height=540'); }
  catch (x) { row('t-win', 'window.open', 'problem', String(x.message || x)); return; }
  row('t-win', 'window.open returned a window object', audience ? 'ok' : 'problem', audience ? '' : 'null: blocked by the browser or by the shell');
  setTimeout(() => { if (!lastReady) row('t-win', 'audience window announced itself', 'problem', 'nothing heard within 2 s on any transport'); }, 2000);
  setTimeout(() => sendAll({ spike: 1, type: 'hello' }), 700);
}
$('b-open').onclick = () => openAudience();
$('b-next').onclick = () => { slide++; sendAll({ spike: 1, type: 'goto', slide }); };
$('b-prev').onclick = () => { slide = Math.max(1, slide - 1); sendAll({ spike: 1, type: 'goto', slide }); };
$('b-close').onclick = () => { try { audience && audience.close(); } catch (_) {} };
$('b-ping').onclick = async () => {
  const lat = { broadcast: [], postMessage: [], storage: [] };
  for (let i = 0; i < 30; i++) {
    const id = 'p' + i + Math.random();
    await new Promise((res) => { const t0 = nowMs(); const to = setTimeout(res, 400); pongs.set(id, (via) => { lat[via].push(nowMs() - t0); clearTimeout(to); res(); }); sendAll({ spike: 1, type: 'ping', id }); });
    await new Promise((r) => setTimeout(r, 30));
  }
  for (const k of Object.keys(lat)) {
    const a = lat[k].sort((x, y) => x - y);
    row('t-win', 'round trip via ' + k, a.length ? 'ok' : 'na', a.length ? `${a.length} answers, median ${a[a.length >> 1].toFixed(1)} ms, max ${a[a.length - 1].toFixed(1)} ms` : 'no answer');
  }
};

// --- screens
let details = null;
$('b-screens').onclick = async () => {
  if (!('getScreenDetails' in window)) { row('t-scr', 'getScreenDetails', 'na', 'not in this web view (the manual route: drag the window, press F11)'); return; }
  try { details = await window.getScreenDetails();
    row('t-scr', 'getScreenDetails', 'ok', details.screens.map((s, i) => `#${i}${s.isPrimary ? '*' : ''} ${s.width}x${s.height} at ${s.left},${s.top} scale ${s.devicePixelRatio}`).join(' | ')); }
  catch (x) { row('t-scr', 'getScreenDetails', 'problem', String(x.name || '') + ' ' + String(x.message || x)); }
};
$('b-open2').onclick = () => {
  if (!details || details.screens.length < 2) { row('t-scr', 'open on the other screen', 'na', 'needs two screens and "List screens" first'); return; }
  const other = details.screens.find((s) => s !== details.currentScreen) || details.screens[1];
  openAudience(`popup=yes,left=${other.availLeft},top=${other.availTop},width=${other.availWidth},height=${other.availHeight}`);
  row('t-scr', 'open on the other screen', 'ok', `asked for ${other.availWidth}x${other.availHeight} at ${other.availLeft},${other.availTop}; check where it landed`);
};

// --- wake lock
$('b-wake').onclick = async () => {
  if (!('wakeLock' in navigator)) { row('t-misc', 'Screen Wake Lock', 'na', 'not in this web view'); return; }
  try { const l = await navigator.wakeLock.request('screen'); row('t-misc', 'Screen Wake Lock', 'ok', 'acquired'); setTimeout(() => l.release(), 10000); }
  catch (x) { row('t-misc', 'Screen Wake Lock', 'problem', String(x.message || x)); }
};

// --- keys
$('keys').innerHTML = '<tr><th>Key</th><th>Received by the page</th></tr>' + KEYS.map(([n]) => `<tr id="k-${n}"><td>${n}</td><td class="na">not yet</td></tr>`).join('');
addEventListener('keydown', (e) => {
  for (const [n, w] of KEYS) if (keyMatches(w, e)) { e.preventDefault(); const tr2 = $('k-' + n); tr2.classList.add('seen'); tr2.lastChild.textContent = `yes (${e.key}${e.repeat ? ', repeat' : ''}) at ${new Date().toLocaleTimeString()}`; R.keys[n] = true; }
});

// --- Neutralino rows: directly (top-level page) or by asking the shell page that frames this one
const canAsk = !!window.Neutralino || framed;
if (canAsk) { $('neu').hidden = false; $('h-neu').hidden = false; }
if (window.Neutralino) { try { Neutralino.init(); } catch (_) {} }
function neuDo(op) {
  if (window.Neutralino && !framed) {
    const p = op === 'setFullScreen' ? Neutralino.window.setFullScreen() : op === 'exitFullScreen' ? Neutralino.window.exitFullScreen()
      : Neutralino.window.create('/audience.html', { title: 'Audience (spike)', width: 960, height: 540, useSavedState: false });
    p.then(() => row('t-neu', op, 'ok', 'direct'), (x) => row('t-neu', op, 'problem', String(x && (x.code || x.message) || x)));
  } else parent.postMessage({ spike: 'ask-shell', op }, '*');
}
addEventListener('message', (e) => { if (e.data && e.data.spike === 'shell-reply') row('t-neu', e.data.op, e.data.ok ? 'ok' : 'problem', 'by the shell page: ' + (e.data.error || '')); });
$('n-fs').onclick = () => neuDo('setFullScreen'); $('n-fs-off').onclick = () => neuDo('exitFullScreen'); $('n-create').onclick = () => neuDo('create');

// --- manual verdicts
const MANUAL = [
  'The audience window shows the slide number I chose with the buttons',
  'The audience window fills the other screen when I drag it there and press F (or F11)',
  'Esc leaves fullscreen, in the main window and in the audience window',
  'The pointer disappears in the audience window after 2 s without moving',
  'Going forward with → or Space in the audience window moves this page too',
  'Fullscreen shows no browser or shell chrome (title bar, menu, address bar)',
  'Nothing flashes or resizes badly when entering and leaving fullscreen',
];
$('manual').innerHTML = '<tr><th>Row</th><th>Verdict</th></tr>' + MANUAL.map((m, i) => `<tr><td>${esc(m)}</td><td>` +
  ['ok', 'problem', 'n/a'].map((v) => `<label><input type="radio" name="m${i}" value="${v}"> ${v}</label> `).join('') + '</td></tr>').join('');
function report() {
  R.when = new Date().toISOString(); R.seenVia = seenVia; R.manual = {};
  MANUAL.forEach((m, i) => { const c = document.querySelector(`input[name=m${i}]:checked`); R.manual[m] = c ? c.value : 'not answered'; });
  R.env.pageLoadsAtReport = sessionStorage.getItem('loads');
  $('report').value = JSON.stringify(R, null, 2); return $('report').value;
}
$('b-report').onclick = report;
$('b-copy').onclick = async () => { const t = report(); try { await navigator.clipboard.writeText(t); } catch (_) { $('report').select(); document.execCommand && document.execCommand('copy'); } };
$('b-dl').onclick = () => { const t = report(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'application/json' })); a.download = 'e10-2-presenter-window-' + Date.now() + '.json'; a.click(); };
