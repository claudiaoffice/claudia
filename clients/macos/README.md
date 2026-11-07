# Claudia for macOS (claudia-shell-macos)

The native client of Claudia for macOS: a thin Neutralino shell around the one web frontend (D42–D44), the same
discipline the Linux client (`clients/linux/`) follows for GTK. Today it contains **Claudia Creates**; composes and
computes follow the same way Linux's did (one more entry in `identity.ts`, one more `apps/<app>/`).

**Read this before anything else:** the one thing this client does that nobody has run on a real Mac yet is
Neutralino injecting its API (`window.Neutralino`, the native menu/event channel) into a page loaded from an
*external* URL rather than from Neutralino's own bundle. That is D159's whole open question. Everything below this
line is built and tested up to that boundary; past it, it is this client's best-effort answer, not a verified one.
**The first thing to do on a real Mac is confirm `window.Neutralino` exists once the window shows the loopback page**
— see "Not verified" below.

```
clients/
  contract/            the shell contract: JSON schema, versioned, shared by every shell (see its README)
  macos/
    src/
      identity.ts       which app, its bundle id, title, server model          (plain Node)
      paths.ts           ~/Library/Application Support/Claudia, frontend/python lookup (plain Node)
      server.ts          start, wait for and stop the local server, freePort() (plain Node)
      menu.ts            the shared GTK manifest -> Neutralino WindowMenuItem  (plain TS)
      page-bridge.ts      D159 option 2: shims window.webkit.messageHandlers   (plain TS; a few real Neutralino calls in installBridge())
      inject-entry.ts    the file Neutralino's injectScript actually loads     (bundled, not run directly)
      launch.ts          prepare the server, find the binary, start both       (Node + child_process)
      generated/         menu.<app>.json, checked in, generated from manifest.py
    tools/
      generate_menu.py   imports clients/linux's manifest.py (no GTK) and writes generated/menu.<app>.json
      build-inject.mjs   esbuild: bundles inject-entry.ts into apps/<app>/inject/claudia-bridge.js
    apps/creates/
      neutralino.config.json, icon.svg/png, inject/claudia-bridge.js (built, not checked in by npm run build)
    tests/
```

## Running it from a checkout

```
uv sync                                    # the server's Python 3.14 environment: .venv
(cd web && npm ci && npm run build)        # the web frontend: web/.output/public
cd clients/macos && npm ci
npm run generate-menu                      # regenerate src/generated/menu.*.json from the shared manifest
npm run build                              # tsc, then bundles apps/creates/inject/claudia-bridge.js
# place a Neutralino 6.8.0 macOS binary (neutralino-mac_arm64 or neutralino-mac_x64) in apps/creates/,
# or set CLAUDIA_NEUTRALINO_BIN to its path
node dist/launch.js creates
```

Documents are kept in `~/Library/Application Support/Claudia/creates/documents` and the server's state in the
sibling `state/` folder. There is no packaged `.app` yet (icon assets exist as PNG; `.icns`, codesigning and
notarization are not done — see "Not done").

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv/bin/python` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web/.output/public` of the checkout (nothing ships a packaged copy yet). If set, it is the only candidate: a wrong path is reported, not replaced. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `neutralino-mac_<arch>` next to `neutralino.config.json` in `apps/<app>/`, not checked into the repo. |

## How it works

* **The server, started by this launcher, not by Neutralino.** `launch.ts` spawns `<server python> -m claudia_server
  --model claudia_creates:SlideModel --host 127.0.0.1 --port <free port> --no-tls --web <frontend> ...` itself (plain
  `node:child_process`, mirroring `server.py`/`launch.py` on Linux) and waits for `/api/health`, **before** the
  Neutralino binary is started at all — the server's address has to exist first, because it becomes the `--url` the
  shell is pointed at.
* **D159 option 2: the window loads that address, not anything Neutralino ships.** The binary runs as
  `claudia-creates --path=apps/creates --url=http://127.0.0.1:<port> --enable-server=true`. `--path` keeps
  `neutralino.config.json` (and its `injectGlobals`/`injectClientLibrary`/`injectScript` settings) in effect; `--url`
  overrides what the window actually shows. `--enable-server=true` is Neutralino's own documented requirement for
  loading a remote/external URL — it is the native-API/WebSocket channel the injected script depends on.
* **The injected script (`inject-entry.ts`, bundled to `apps/creates/inject/claudia-bridge.js`) is the whole
  adapter.** It shims `window.webkit.messageHandlers.claudia.postMessage` to look exactly like the WebKitGTK handler
  `web/app/lib/shell-bridge.ts`'s own `detectHandler()` already looks for — so **the web app needs zero changes** for
  a second shell, the same way D121 put the contract client directly in the page for the first one. It answers
  `hello` with `welcome` itself (there is no separate native shell process to round-trip to: this script *is* the
  shell, running inside the page), builds the native menu from the generated manifest JSON, and turns
  `mainMenuItemClicked` into contract `action` messages.
* **The shared menu manifest, one more consumer.** `manifest.py` (`clients/linux/src/claudia_shell_gtk/manifest.py`)
  stays the one source of truth for File/Edit/Format/View/Tools/Config/Help across every app and shell; `role` (the
  Cocoa selector D158 needs — `undo:`, `redo:`, `cut:`, `copy:`, `paste:`) was added to it rather than duplicated
  here. `generate_menu.py` imports it (no GTK, by the same discipline `manifest.py` was already built to) and writes
  `src/generated/menu.<app>.json`; `menu.ts` turns that into Neutralino's `WindowMenuItem[]`, relocating `help.about`
  and `file.quit` into a leading application menu (D44) and mapping each Edit role to its Cocoa selector and
  `ROLE_SHORTCUT` accelerator.
* **Quit is native; About is not.** `page-bridge.ts`'s `routeMenuClick()` sends `file.quit` straight to
  `Neutralino.app.exit()`. `help.about` is `Kind.SHELL` in the manifest (GTK shows its own dialog for it), but
  Neutralino has no native About panel (D158 point 4), so it is forwarded to the page like any other action —
  `AboutDialog.vue` already exists and needs no change.

## Tests

```
cd clients/macos
npm test              # vitest: identity, paths, server (incl. freePort), menu, page-bridge, launch — 50 tests
npm run typecheck      # tsc --strict over src/ and tests/
python3 -m pytest tools/tests   # generate_menu.py: 9 tests
ruff check . && ruff format --check . && mypy tools
npm run check-menu     # fails if src/generated/menu.*.json has drifted from manifest.py
```

Nothing here starts a real Neutralino binary or opens a real window — `installBridge()` in `page-bridge.ts` is the
one function with no test of its own, because what it calls only exists once `window.Neutralino` is real (see "Not
verified"). Everything pure around it (`routeMenuClick`, `applyActionStates`, `nextCheckedTarget`, the whole of
`menu.ts`) is tested without one.

## Not verified (needs a real Mac)

1. **D159's core mechanic.** Whether `injectGlobals`/`injectClientLibrary`/`injectScript` (confirmed as real
   Neutralino config fields and CLI flags against its own docs) actually reach a page Neutralino did not itself
   serve — i.e. whether `window.Neutralino` exists at all once the window shows the loopback URL. If it does not,
   D159 needs its first option instead (Neutralino serves its own bundle, the page opens a cross-origin WebSocket to
   the document server, `--allow-origin` and a fixed port follow).
2. **The dual native-Cocoa-action-plus-page-dispatch interaction** for creates' own `lib/clipboard.ts` on a real
   slide canvas — the spike only confirmed this on a generic text field, not Creates' editor.
3. **No Redo shortcut.** `ROLE_SHORTCUT` in `menu.ts` has no `redo:` entry; no confirmed Neutralino grammar for
   Cmd+Shift+Z was found. Redo still works by clicking the menu item.
4. **Orphaned server processes.** No PDEATHSIG equivalent on macOS and no `--lifeline` flag in the real
   `claudia_server` package (unlike the spike's own throwaway `testserver.py`), so `stop()` only has SIGTERM/SIGKILL
   — what happens to the server if the Neutralino window is killed outright, rather than closed, is untested.
5. **A clean machine.** Only whatever Mac the E0.3 spike ran on; no second Mac, no older macOS, no screen reader.

## Not done

Packaging (a real `.app` bundle, `.icns`, codesigning, notarization, a DMG or installer); composes and computes (only
`creates` has an `apps/<app>/` folder — `packaged: false` in `identity.ts` for the other two); printing as a contract
message (D158 point 2 — `Neutralino.window.print()` exists and is in `NeutralinoLike`, but nothing calls it yet);
`nativeAllowList`/`filesystemScopes` are trimmed to the four methods this client actually calls today
(`app.exit`, `window.setMainMenu`, `window.print`, `events.on`) but have not been re-checked against a later
Neutralino upgrade (D157 asks for that on every version bump); translations; single-instance behaviour.
