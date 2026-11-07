// A spike's own request/response bridge, NOT the shell contract of clients/contract (that one is message based and
// the page speaks it in web/app/lib/shell-bridge.ts). This file only exists to drive the Neutralino API from a test page:
// one API for the page, two implementations: the Neutralino shell and a plain browser (fallbacks).
//
//   await shell.ready                     -> info object ({kind, os, nativeMenu, ...})
//   await shell.call(method, params)      -> result (throws on error)
//   shell.on('action'|'theme'|..., fn)    -> events from the shell
//
// Methods: hello, ping, menu.set, file.open, file.save, about.show, window.print, theme.get,
//          server.start, server.stop, report.write, app.quit
(function () {
  "use strict";
  const listeners = {};
  const pending = new Map();
  let nextId = 1;

  function emit(name, detail) {
    (listeners[name] || []).forEach(function (fn) {
      try { fn(detail); } catch (e) { console.error(e); }
    });
  }
  function on(name, fn) { (listeners[name] = listeners[name] || []).push(fn); }

  const hasNeu = typeof window.NL_OS !== "undefined" && typeof window.Neutralino !== "undefined";
  const kind = hasNeu ? "neutralino" : "browser";

  let impl;

  // ---------------------------------------------------------------- Neutralino
  if (kind === "neutralino") {
    let serverProc = null;
    let serverResolve = null;
    let serverFailed = null;
    const N = window.Neutralino;
    N.init();

    // On macOS the menu is the application menu, and Cmd+C/V/X/A/Z only reach the web view when the items carry
    // the standard Cocoa actions (see the setMainMenu docs). Elsewhere the page handles roles itself.
    const COCOA = { undo: "undo:", redo: "redo:", cut: "cut:", copy: "copy:", paste: "paste:", selectall: "selectAll:" };
    const toMenu = function (manifest) {
      const mac = window.NL_OS === "Darwin";
      return manifest.menus.map(function (m) {
        return { id: m.id, text: m.label, menuItems: m.items.map(function (i) {
          const o = { id: i.id, text: i.label };
          if (mac && i.role && COCOA[i.role]) o.action = COCOA[i.role];
          if (mac && i.accel) o.shortcut = i.accel;
          return o;
        }) };
      });
    };
    N.events.on("mainMenuItemClicked", function (e) { emit("action", { id: e.detail.id }); });
    N.events.on("spawnedProcess", function (e) {
      if (!serverProc || e.detail.id !== serverProc.id) return;
      if (e.detail.action === "stdOut") {
        const m = /PORT (\d+)/.exec(e.detail.data || "");
        if (m && serverResolve) { serverResolve({ port: parseInt(m[1], 10) }); serverResolve = null; }
      } else if (e.detail.action === "exit" && serverFailed) {
        serverFailed("process exited with code " + e.detail.data);
      } else if (e.detail.action === "stdErr" && serverFailed && /not (found|recognized)|No such file/i.test(e.detail.data || "")) {
        serverFailed((e.detail.data || "").trim().slice(0, 120));
      }
    });
    const quote = function (p) { return '"' + p + '"'; };

    const methods = {
      hello: async function () {
        return { kind: "neutralino", os: window.NL_OS, version: window.NL_VERSION || "?", nativeMenu: true,
                 nativeAbout: false, nativeFileDialogs: true, canStartServer: true, rolesNative: window.NL_OS === "Darwin" };
      },
      // a real round trip over the WebSocket to the framework core (the first version answered in JS and measured nothing)
      ping: async function (p) { await N.computer.getArch(); return { t: p.t }; },
      "menu.set": async function (p) { await N.window.setMainMenu(toMenu(p)); return { ok: true }; },
      "file.open": async function (p) {
        const paths = await N.os.showOpenDialog(p.title || "Open", { multiSelections: false });
        if (!paths || !paths.length) return { cancelled: true };
        const path = paths[0];
        const text = await N.filesystem.readFile(path);
        return { path: path, name: path.split(/[\\/]/).pop(), size: text.length, text: text.slice(0, 100000) };
      },
      "file.save": async function (p) {
        const path = await N.os.showSaveDialog(p.title || "Save As", { defaultPath: p.suggestedName || "untitled.txt" });
        if (!path) return { cancelled: true };
        await N.filesystem.writeFile(path, p.text || "");
        return { path: path };
      },
      "about.show": async function () { return { handled: false }; },
      "window.print": async function () { await N.window.print(); return {}; },
      "theme.get": async function () { return { dark: window.matchMedia("(prefers-color-scheme: dark)").matches }; },
      "server.start": async function () {
        // Tries uv first (E0.2 launcher), then plain Python. --lifeline makes the server exit when its stdin closes.
        const script = quote(window.NL_PATH + "/server/testserver.py") + " --port 0 --lifeline";
        const candidates = ["uv run --no-project python ", (window.NL_OS === "Windows" ? "py -3 " : "python3 "), "python "];
        const errors = [];
        for (const prefix of candidates) {
          const outcome = await new Promise(async function (resolve) {
            const timer = setTimeout(function () { resolve({ error: "no port within 20 s" }); }, 20000);
            serverResolve = function (v) { clearTimeout(timer); resolve(v); };
            serverFailed = function (why) { clearTimeout(timer); resolve({ error: why }); };
            try { serverProc = await N.os.spawnProcess(prefix + script); }
            catch (e) { clearTimeout(timer); resolve({ error: e.message || String(e) }); }
          });
          serverResolve = null; serverFailed = null;
          if (outcome.port) return outcome;
          errors.push(prefix.trim() + ": " + outcome.error);
          try { if (serverProc) await N.os.updateSpawnedProcess(serverProc.id, "exit"); } catch (e) { /* already gone */ }
          serverProc = null;
        }
        throw new Error("could not start the test server. " + errors.join("; "));
      },
      "server.stop": async function () {
        if (serverProc) {
          const id = serverProc.id; serverProc = null;
          try { await N.os.updateSpawnedProcess(id, "stdInEnd"); } catch (e) { /* ignore */ }
          await new Promise(function (r) { setTimeout(r, 600); });
          try { await N.os.updateSpawnedProcess(id, "exit"); } catch (e) { /* already exited */ }
        }
        return { stopped: true };
      },
      "report.write": async function () { return { path: null, note: "use the Save report button" }; },
      "app.quit": async function () { await N.app.exit(); return {}; }
    };
    impl = async function (method, params) {
      const f = methods[method];
      if (!f) throw new Error("not implemented in the Neutralino shell: " + method);
      return await f(params || {});
    };
  }

  // ---------------------------------------------------------------- browser fallbacks
  if (kind === "browser") {
    let serverUrl = null;
    const methods = {
      hello: async function () {
        return { kind: "browser", os: navigator.platform, nativeMenu: false, nativeAbout: false,
                 nativeFileDialogs: false, canStartServer: false };
      },
      ping: async function (p) { return { t: p.t }; },
      "menu.set": async function () { return { ok: true, note: "browser draws its own menu" }; },
      "file.open": function (p) {
        return new Promise(function (resolve) {
          const input = document.createElement("input");
          input.type = "file";
          input.onchange = async function () {
            const f = input.files[0];
            if (!f) return resolve({ cancelled: true });
            const text = await f.text();
            resolve({ path: f.name, name: f.name, size: f.size, text: text.slice(0, 100000) });
          };
          input.oncancel = function () { resolve({ cancelled: true }); };
          input.click();
        });
      },
      "file.save": async function (p) {
        const blob = new Blob([p.text || ""], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = p.suggestedName || "untitled.txt";
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
        return { path: a.download };
      },
      "about.show": async function () { return { handled: false }; },
      "window.print": async function () { window.print(); return {}; },
      "theme.get": async function () { return { dark: window.matchMedia("(prefers-color-scheme: dark)").matches }; },
      "server.start": async function () {
        const q = new URLSearchParams(location.search).get("server");
        if (!q) throw new Error("add ?server=http://127.0.0.1:PORT to the address to test a running testserver.py");
        serverUrl = q;
        return { port: parseInt(new URL(q).port, 10) };
      },
      "server.stop": async function () { serverUrl = null; return { stopped: true }; },
      "report.write": async function () { return { path: null }; },
      "app.quit": async function () { window.close(); return {}; }
    };
    impl = async function (method, params) {
      const f = methods[method];
      if (!f) throw new Error("not implemented in the browser: " + method);
      return await f(params || {});
    };
  }

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
    emit("theme", { dark: e.matches });
  });

  const shell = {
    kind: kind,
    call: function (method, params) { return impl(method, params); },
    on: on,
    info: null
  };
  shell.ready = shell.call("hello").then(function (info) { shell.info = info; return info; });
  window.claudiaShell = shell;
})();
