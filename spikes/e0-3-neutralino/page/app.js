// Test page for the E0.3 / E0.8 shell comparison. No framework on purpose.
(function () {
  "use strict";
  const shell = window.claudiaShell;
  const manifest = window.CLAUDIA_MANIFEST;
  const $ = function (s, r) { return (r || document).querySelector(s); };
  const sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  const t0 = performance.now();
  const selftest = new URLSearchParams(location.search).has("selftest");

  const results = {};            // id -> { title, status, detail, verdict, note }
  const counts = { hover: 0, click: 0, relayout: 0 };
  const actionsSeen = new Set();
  const envInfo = {};

  // ------------------------------------------------------------------ helpers
  function log() {
    const line = "[" + ((performance.now() - t0) / 1000).toFixed(2) + "] " + Array.prototype.slice.call(arguments).join(" ");
    const el = $("#log");
    el.textContent += line + "\n";
    el.scrollTop = el.scrollHeight;
    console.log(line);
  }
  const pass = function (detail) { return { status: "pass", detail: detail || "" }; };
  const fail = function (detail) { return { status: "fail", detail: detail || "" }; };
  const info = function (detail) { return { status: "info", detail: detail || "" }; };

  // deterministic pseudo random numbers, so every shell plots the same data
  function rng(seed) {
    let s = seed >>> 0;
    return function () { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  }

  function webglInfo() {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") || c.getContext("webgl");
    if (!gl) return null;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    return { version: gl.getParameter(gl.VERSION), renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER) };
  }

  // ------------------------------------------------------------------ environment
  function fillEnv() {
    const gl = webglInfo();
    envInfo.shell = shell.kind + " " + JSON.stringify(shell.info || {});
    envInfo.userAgent = navigator.userAgent;
    envInfo.platform = navigator.platform + " / " + navigator.language;
    envInfo.display = "devicePixelRatio " + window.devicePixelRatio + ", screen " + screen.width + "x" + screen.height;
    envInfo.window = window.innerWidth + "x" + window.innerHeight;
    envInfo.colorScheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    envInfo.webgl = gl ? gl.version + " / " + gl.renderer : "not available";
    envInfo.plotly = "plotly.js " + (window.Plotly ? window.Plotly.version : "missing");
    envInfo.readyAfterSeconds = ((performance.now() - t0) / 1000).toFixed(2);
    const labels = { shell: "Shell", userAgent: "User agent", platform: "Platform / language", display: "Display", window: "Window (CSS px)",
                     colorScheme: "Colour scheme", webgl: "WebGL", plotly: "Charts", readyAfterSeconds: "Page ready after (s)" };
    const t = $("#env");
    t.innerHTML = "";
    Object.keys(labels).forEach(function (k) {
      const tr = document.createElement("tr");
      const a = document.createElement("td"); a.textContent = labels[k];
      const b = document.createElement("td"); b.textContent = envInfo[k]; b.id = "env-" + k;
      tr.appendChild(a); tr.appendChild(b); t.appendChild(tr);
    });
  }
  window.addEventListener("resize", function () {
    envInfo.window = window.innerWidth + "x" + window.innerHeight + " (dpr " + window.devicePixelRatio + ")";
    const el = $("#env-window"); if (el) el.textContent = envInfo.window;
  });

  // ------------------------------------------------------------------ charts
  const hooked = new Set();
  function hook(div) {
    if (hooked.has(div.id)) return;
    hooked.add(div.id);
    ["hover", "click", "relayout"].forEach(function (n) {
      div.on("plotly_" + n, function () { counts[n]++; $("#c-" + n).textContent = counts[n]; });
    });
  }
  function baseLayout(title) {
    return {
      title: { text: title, font: { size: 15 } },
      font: { family: "ClaudiaTestFont, system-ui, sans-serif", color: getComputedStyle(document.body).color },
      margin: { t: 48, l: 48, r: 16, b: 40 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", autosize: true
    };
  }
  async function plot(id, data, layout, title) {
    const div = $("#ch-" + id);
    const s = performance.now();
    await Plotly.react(div, data, Object.assign(baseLayout(title), layout || {}), { responsive: true, displaylogo: false });
    const ms = performance.now() - s;
    hook(div);
    return { ms: ms, svg: !!div.querySelector(".main-svg"), canvas: !!div.querySelector("canvas") };
  }

  async function chartBar() {
    const r = await plot("bar", [{ type: "bar", x: ["Mon", "Tue", "Wed", "Thu", "Fri"], y: [3, 7, 4, 9, 6], marker: { color: "#5B4BC4" } }], {}, "Bar chart (label in the bundled font)");
    return r.svg ? pass(r.ms.toFixed(0) + " ms") : fail("no SVG produced");
  }
  async function chartLine() {
    const rand = rng(7), x = [], y = []; let v = 0;
    for (let i = 0; i < 60; i++) { v += rand() - 0.45; x.push(i); y.push(v); }
    const r = await plot("line", [{ type: "scatter", mode: "lines+markers", x: x, y: y, line: { color: "#2a9d8f" } }], {}, "Line chart");
    return r.svg ? pass(r.ms.toFixed(0) + " ms") : fail("no SVG produced");
  }
  async function chartGl() {
    if (!webglInfo()) return fail("WebGL not available in this web view");
    const rand = rng(11), x = new Float32Array(100000), y = new Float32Array(100000);
    for (let i = 0; i < x.length; i++) {
      x[i] = (rand() + rand() + rand() + rand() - 2) * 2; y[i] = (rand() + rand() + rand() + rand() - 2) * 2;
    }
    const r = await plot("gl", [{ type: "scattergl", mode: "markers", x: Array.from(x), y: Array.from(y), marker: { size: 2, opacity: 0.35, color: "#D85A30" } }], {}, "100,000 points (scattergl)");
    return r.canvas ? pass(r.ms.toFixed(0) + " ms") : fail("no canvas produced");
  }
  async function chartHeat() {
    const z = [];
    for (let i = 0; i < 120; i++) { const row = []; for (let j = 0; j < 120; j++) row.push(Math.sin(i / 9) * Math.cos(j / 7)); z.push(row); }
    const r = await plot("heat", [{ type: "heatmap", z: z, colorscale: "Viridis" }], {}, "Heatmap 120 x 120");
    return r.svg ? pass(r.ms.toFixed(0) + " ms") : fail("no SVG produced");
  }
  async function chartEvents() {
    // Plotly emits plotly_hover only for real pointer input, so the automatic part checks the relayout
    // event and that a programmatic hover draws its label; real hover/click are in the manual part.
    const div = $("#ch-bar"), before = counts.relayout;
    await Plotly.relayout(div, { "xaxis.range": [-0.5, 3.5] });
    try { Plotly.Fx.hover(div, [{ curveNumber: 0, pointNumber: 1 }]); } catch (e) { return fail("Fx.hover threw: " + e.message); }
    await sleep(200);
    const label = div.querySelectorAll(".hoverlayer .hovertext").length;
    const ok = counts.relayout > before && label > 0;
    return ok ? pass("relayout event arrived, hover label drawn") : fail("relayout events " + (counts.relayout - before) + ", hover labels " + label);
  }

  // ------------------------------------------------------------------ fonts and server
  async function fontBundled() {
    const f = new FontFace("ClaudiaTestFont", "url(fonts/bundled-test-font.ttf)");
    await f.load(); document.fonts.add(f);
    return pass("loaded from the bundled page; check that the first chart title is italic serif");
  }
  async function withServer(fn) {
    const started = await shell.call("server.start");
    const base = "http://127.0.0.1:" + started.port;
    try { return await fn(base); } finally { await shell.call("server.stop"); }
  }
  async function serverRoundTrip() {
    return withServer(async function (base) {
      const s = performance.now();
      const r = await fetch(base + "/ping");
      const j = await r.json();
      return j.ok ? pass("started, answered /ping in " + (performance.now() - s).toFixed(0) + " ms, stopped. After the run check that no server process is left.") : fail("bad answer");
    });
  }
  async function fontServer() {
    return withServer(async function (base) {
      const f = new FontFace("ServerFont", "url(" + base + "/fonts/ServerFont.ttf)");
      await f.load(); document.fonts.add(f);
      const ok = document.fonts.check("16px ServerFont");
      return ok ? pass("font loaded from the local server (cross-origin); the words 'server font' in the text box turn bold serif") : fail("font did not load");
    });
  }

  // ------------------------------------------------------------------ shell checks
  async function shellHello() { return pass(JSON.stringify(shell.info)); }
  async function shellPing() {
    const times = [];
    for (let i = 0; i < 30; i++) { const s = performance.now(); await shell.call("ping", { t: i }); times.push(performance.now() - s); }
    times.sort(function (a, b) { return a - b; });
    return pass("30 round trips, median " + times[15].toFixed(1) + " ms, slowest " + times[29].toFixed(1) + " ms");
  }
  async function shellMenu() {
    const r = await shell.call("menu.set", manifest);
    return pass(JSON.stringify(r) + (shell.info && shell.info.nativeMenu ? " (native menu)" : " (page draws the menu)"));
  }
  async function shellTheme() {
    const r = await shell.call("theme.get");
    return pass("shell reports dark=" + r.dark + ", page sees " + envInfo.colorScheme);
  }

  async function openFile() {
    const r = await shell.call("file.open", { title: "Open a text file" });
    if (r.cancelled) { log("open: cancelled"); return info("cancelled"); }
    log("open:", r.name, r.size, "characters; first line:", (r.text || "").split("\n")[0].slice(0, 60));
    return pass(r.name + ", " + r.size + " characters");
  }
  async function saveFile() {
    const r = await shell.call("file.save", { title: "Save test file", suggestedName: "claudia-shell-test-äöü.txt", text: "Claudia shell test\nÄpfel € 日本語\n" });
    if (r.cancelled) { log("save: cancelled"); return info("cancelled"); }
    log("save:", r.path);
    return pass("written to " + r.path + "; open it and check the umlauts, euro sign and Japanese text");
  }
  async function showAbout() {
    const r = await shell.call("about.show", manifest.app);
    if (r.handled) return pass("native About dialog");
    let d = $("#about-dialog");
    if (!d) {
      d = document.createElement("dialog"); d.id = "about-dialog";
      d.innerHTML = "<h2></h2><p></p><form method='dialog'><button class='primary'>Close</button></form>";
      document.body.appendChild(d);
    }
    $("h2", d).textContent = manifest.app.name + " " + manifest.app.version;
    $("p", d).textContent = manifest.app.comments;
    d.showModal();
    return pass("page dialog (shared web component stand-in)");
  }

  // ------------------------------------------------------------------ check table
  const CHECKS = [
    { id: "shell.hello", title: "Shell contract: hello", auto: shellHello },
    { id: "shell.ping", title: "Shell contract: round-trip time", auto: shellPing },
    { id: "font.bundled", title: "Font from the bundled page", auto: fontBundled },
    { id: "plotly.bar", title: "Plotly bar chart", auto: chartBar },
    { id: "plotly.line", title: "Plotly line chart", auto: chartLine },
    { id: "plotly.gl", title: "Plotly 100,000 points (WebGL)", auto: chartGl },
    { id: "plotly.heat", title: "Plotly heatmap", auto: chartHeat },
    { id: "plotly.events", title: "Plotly events and hover", auto: chartEvents,
      manual: "Move the mouse over the bar chart, click a bar, drag to zoom, double-click to reset, scroll the wheel over a chart. The counters above the charts must increase and the chart must feel smooth." },
    { id: "shell.server", title: "Local server: start, answer, stop", auto: serverRoundTrip },
    { id: "font.server", title: "Font delivered by the local server (D26)", auto: fontServer },
    { id: "shell.menu", title: "Menu from the manifest", auto: shellMenu,
      manual: "The menu is the OS-native one on Windows and macOS (in a browser the page draws it). Click every item: a line 'action …' must appear in the log. Check shortcuts and the macOS application menu." },
    { id: "shell.file", title: "File dialogs", extra: [{ label: "Open file…", run: openFile }, { label: "Save test file…", run: saveFile }],
      manual: "Open a text file whose path has spaces and umlauts, then save the test file and open it in an editor. Are the dialogs native? Do they remember folders?" },
    { id: "shell.about", title: "About dialog", extra: [{ label: "Show About", run: showAbout }],
      manual: "Does it look native or like a page dialog? Is it modal and does Escape close it?" },
    { id: "shell.theme", title: "Dark and light mode", auto: shellTheme,
      manual: "Switch the OS between light and dark while this window is open. The page colours must follow without reload." },
    { id: "m.input.dead", title: "Dead keys and AltGr", manual: "In the single-line field and the editable block: ´ then e, ` then a, ^ then o, AltGr+E (€), AltGr+Q (@), AltGr+7 ({)." },
    { id: "m.input.ime", title: "Input method (Japanese or Chinese)", manual: "Type with an IME in both fields. The candidate window must appear next to the caret, composition must show inline, and Enter must not trigger anything while composing." },
    { id: "m.input.clip", title: "Clipboard", manual: "Copy text from another application into the editable block (plain and rich), copy out of it, use Ctrl/Cmd+C, V, X, A and the Edit menu." },
    { id: "m.input.spell", title: "Spellcheck and context menu", manual: "Type a misspelled word in the editable block. Is it underlined? Does the right-click menu offer suggestions?" },
    { id: "m.dnd", title: "Drag and drop of text", manual: "Select text in the block and drag it elsewhere in the block; drag text from another application into it." },
    { id: "m.a11y", title: "Screen reader", manual: "Orca, NVDA/Narrator or VoiceOver: does it read the fields, the buttons of this page and the menu? Are caret moves announced? Is the mock panel's toggle button announced as expanded or collapsed?" },
    { id: "m.window", title: "Window behaviour", manual: "Resize by dragging every edge and corner, maximise, restore, minimise, full screen, Windows 11 snap layouts (hover over maximise), GNOME tiling (Super+arrow), double-click on the title bar. Does the layout reflow?" },
    { id: "m.hidpi", title: "Display scale", manual: "Run at 100% and 150% (or 200%). Is text sharp? Is the chart sharp? Move the window between screens of different scale if you can." },
    { id: "m.panel", title: "Docked panel", manual: "Click the arrow on the panel's left border: the panel hides and shows, the main area takes the room, nothing is overlapped." },
    { id: "m.print", title: "Printing", extra: [
      { label: "Print via shell", run: async function () { await shell.call("window.print"); return info("shell print requested"); } },
      { label: "Browser window.print()", run: async function () { window.print(); return info("window.print() called"); } }],
      manual: "Try both buttons. Does a native print dialog appear, and does the preview show the page? (Neutralino's docs say the macOS web view does not implement window.print(); its own window.print() API is the documented replacement.)" },
    { id: "m.focus", title: "Focus and keyboard", manual: "Tab through the page: the focus ring is visible and the order is sensible. Do menu accelerators and page shortcuts both work?" },
    { id: "m.start", title: "Start time and size", manual: "Write down: seconds from launch to a visible window, seconds to the first chart, and the size of the installed shell (without the bundled page)." }
  ];

  function renderChecks() {
    const box = $("#checks");
    box.innerHTML = "";
    CHECKS.forEach(function (c) {
      results[c.id] = results[c.id] || { title: c.title, status: "", detail: "", verdict: "", note: "" };
      const row = document.createElement("div");
      row.className = "row"; row.id = "row-" + c.id;
      const h = document.createElement("div"); h.className = "bar";
      const title = document.createElement("h3"); title.textContent = c.title; h.appendChild(title);
      const badge = document.createElement("span"); badge.className = "badge"; badge.id = "badge-" + c.id; badge.textContent = c.auto ? "not run" : "manual"; h.appendChild(badge);
      if (c.auto) {
        const b = document.createElement("button"); b.textContent = "Run";
        b.onclick = function () { runCheck(c); }; h.appendChild(b);
      }
      (c.extra || []).forEach(function (x) {
        const b = document.createElement("button"); b.textContent = x.label;
        b.onclick = async function () {
          try { const r = await x.run(); setResult(c, r); } catch (e) { setResult(c, fail(e.message)); }
        };
        h.appendChild(b);
      });
      row.appendChild(h);
      if (c.manual) { const p = document.createElement("p"); p.textContent = c.manual; row.appendChild(p); }
      const d = document.createElement("div"); d.className = "detail"; d.id = "detail-" + c.id; row.appendChild(d);
      const v = document.createElement("div"); v.className = "verdict"; v.setAttribute("role", "radiogroup"); v.setAttribute("aria-label", "Verdict for " + c.title);
      [["ok", "works"], ["problem", "problem"], ["na", "not applicable"]].forEach(function (o) {
        const lab = document.createElement("label"); const r = document.createElement("input");
        r.type = "radio"; r.name = "v-" + c.id; r.value = o[0];
        r.onchange = function () { results[c.id].verdict = o[0]; };
        lab.appendChild(r); lab.appendChild(document.createTextNode(" " + o[1])); v.appendChild(lab);
      });
      row.appendChild(v);
      const n = document.createElement("input"); n.type = "text"; n.className = "note"; n.placeholder = "Notes"; n.setAttribute("aria-label", "Notes for " + c.title);
      n.oninput = function () { results[c.id].note = n.value; };
      row.appendChild(n);
      box.appendChild(row);
    });
  }

  function setResult(c, r) {
    results[c.id].status = r.status; results[c.id].detail = r.detail;
    const badge = document.getElementById("badge-" + c.id);
    badge.textContent = r.status; badge.className = "badge " + r.status;
    document.getElementById("detail-" + c.id).textContent = r.detail;
    log(c.id, r.status, r.detail);
  }
  async function runCheck(c) {
    const badge = document.getElementById("badge-" + c.id); badge.textContent = "running…";
    try { setResult(c, await c.auto()); } catch (e) { setResult(c, fail(String(e && e.message || e))); }
  }
  async function runAll() {
    for (const c of CHECKS) { if (c.auto) await runCheck(c); }
  }

  // ------------------------------------------------------------------ report
  function buildReport() {
    return {
      schema: "claudia-e0-3-report/1",
      when: new Date().toISOString(),
      shell: shell.kind, shellInfo: shell.info, env: envInfo, counts: counts,
      actionsSeen: Array.from(actionsSeen), notes: $("#notes").value,
      checks: CHECKS.map(function (c) { const r = results[c.id]; return { id: c.id, title: c.title, status: r.status, detail: r.detail, verdict: r.verdict, note: r.note }; })
    };
  }
  async function saveReport() {
    const rep = buildReport();
    const stamp = new Date().toISOString().replace(/[:T]/g, "-").slice(0, 16);
    const name = "e0-3-" + shell.kind + "-" + String((shell.info && shell.info.os) || "os").replace(/\W+/g, "") + "-" + stamp + ".json";
    const r = await shell.call("file.save", { title: "Save report", suggestedName: name, text: JSON.stringify(rep, null, 2) });
    $("#save-status").textContent = r.cancelled ? "cancelled" : "saved: " + (r.path || name);
  }

  // ------------------------------------------------------------------ menu, panel, events
  const ROLE_COMMAND = { "edit.undo": "undo", "edit.redo": "redo", "edit.cut": "cut", "edit.copy": "copy", "edit.paste": "paste", "edit.selectall": "selectAll" };
  function handleAction(id) {
    actionsSeen.add(id);
    // macOS wires roles in the shell (Cocoa actions); this is the best-effort fallback (browser menu, Windows)
    if (ROLE_COMMAND[id] && !(shell.info && shell.info.rolesNative)) {
      try { log("execCommand", ROLE_COMMAND[id], document.execCommand(ROLE_COMMAND[id])); } catch (e) { log("execCommand failed:", e.message); }
      return;
    }
    switch (id) {
      case "file.open": openFile().catch(function (e) { log("open failed:", e.message); }); break;
      case "file.save": case "file.saveas": saveFile().catch(function (e) { log("save failed:", e.message); }); break;
      case "file.quit": shell.call("app.quit"); break;
      case "help.about": showAbout().catch(function (e) { log("about failed:", e.message); }); break;
      default: break;
    }
  }
  function renderWebBar() {
    const bar = $("#webbar"); bar.hidden = false; bar.innerHTML = "";
    manifest.menus.forEach(function (m) {
      const d = document.createElement("details"); const s = document.createElement("summary"); s.textContent = m.label; d.appendChild(s);
      const box = document.createElement("div"); box.className = "menu";
      m.items.forEach(function (i) {
        const b = document.createElement("button"); b.textContent = i.label;
        b.onclick = function () { d.open = false; log("action", i.id); handleAction(i.id); };
        box.appendChild(b);
      });
      d.appendChild(box); bar.appendChild(d);
    });
  }
  $("#panel-toggle").onclick = function () {
    const p = $("#panel"); p.classList.toggle("collapsed");
    const open = !p.classList.contains("collapsed");
    $("#panel-toggle").setAttribute("aria-expanded", String(open));
    $("#panel-toggle").textContent = open ? "›" : "‹";
  };
  $("#run-all").onclick = function () { runAll(); };
  $("#save-report").onclick = function () { saveReport().catch(function (e) { $("#save-status").textContent = "failed: " + e.message; }); };

  shell.on("action", function (d) { log("action", d.id); handleAction(d.id); });
  shell.on("theme", function (d) { log("theme event: dark =", d.dark); });

  // ------------------------------------------------------------------ start
  (async function main() {
    renderChecks();
    try { await shell.ready; } catch (e) { log("shell hello failed:", e.message); }
    fillEnv();
    log("shell:", shell.kind, JSON.stringify(shell.info));
    if (!(shell.info && shell.info.nativeMenu)) renderWebBar();
    try { await shell.call("menu.set", manifest); } catch (e) { log("menu.set failed:", e.message); }
    try { await fontBundled(); } catch (e) { log("bundled font failed:", e.message); }
    if (!selftest) {
      // draw the charts straight away so the page is useful at first sight
      for (const c of CHECKS.filter(function (x) { return /^plotly\.(bar|line|gl|heat)$/.test(x.id); })) await runCheck(c);
    }
    if (selftest) {
      log("selftest: running all automatic checks");
      await runAll();
      const rep = buildReport();
      rep.selftest = true;
      try { const w = await shell.call("report.write", rep); log("report written:", w.path); } catch (e) { log("report.write failed:", e.message); }
      await sleep(200);
      await shell.call("app.quit");
    }
  })();
})();
