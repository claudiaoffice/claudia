# Changelog of the Windows client

Newest first. The shell contract has its own version (`clients/contract/`); this file does not repeat it.

## [0.1.0] - unreleased

First version of the native Windows client (E5.11), for composes only, carrying over D159's loopback option
("Neutralino's window points at the document server's own loopback URL, like Linux's shell does, and Neutralino's
API is injected into that external page") rather than asking the transport question again for a second platform —
nothing in the spike or the macOS build found an OS split in that answer.

### Added
- `identity.ts`: which Windows apps exist, their application id, title and server model
  (`de.claudiaoffice.composes` / `claudia_composes:TextModel` for this first version; computes/creates listed but
  not yet `packaged` — the inverse of macOS, where creates was the first app built).
- `paths.ts`: `%LOCALAPPDATA%\Claudia\<app>\{documents,state}` (Windows's own convention, not XDG or
  `~/Library`), `findFrontend`/`findServerPython` with the same `CLAUDIA_WEB_DIR`/`CLAUDIA_SERVER_PYTHON` escape
  hatches the Linux and macOS clients have; `findServerPython` looks for `.venv\Scripts\python.exe` (`uv sync`'s
  own layout on Windows, not `.venv/bin/python`).
- `server.ts`: `LocalServer` (spawn/checkReady/stop) and `freePort()`, adapted from `clients/macos/src/server.ts`
  for a platform with no real signals — `stop()` keeps the same two-argument shape as Linux and macOS for
  interface parity, but makes exactly one `kill()` call: Node's own docs say `ChildProcess.kill()` ignores the
  `signal` argument on Windows and always terminates outright, so there is no softer first step to send before a
  harder second one. Flagged in the README's "Not done" as a real product gap (no graceful shutdown for
  `claudia_server` on a hard kill), not just an implementation detail.
- `launch.ts`: `prepareServer()` (mirrors `launch.py`'s and the macOS client's own two `SetupProblem` messages and
  folder creation), `findNeutralinoBinary()`/`neutralinoBinaryName()` (fixed to `neutralino-win_x64.exe` — unlike
  macOS's, no architecture branch, because Neutralino 6.8.0 publishes only one Windows binary), `buildShellCommand()`
  (`--path`/`--url`/`--enable-server`, identical flags to macOS — Neutralino's own, not OS-specific), and `main()`
  tying server start, binary discovery and the shell process together. No `app-bundle.ts`: the `CFBundleName`
  problem it solves on macOS has no Windows equivalent (the taskbar and title bar already read
  `neutralino.config.json`'s `modes.window.title` directly).
- `menu.ts`: the shared GTK manifest (`manifest.py`'s `describe()` output, read via `generate_menu.py`) turned
  into Neutralino `WindowMenuItem[]`, deliberately simpler than macOS's: `buildMainMenu()` keeps the manifest's
  own menu order with **no relocation** into a leading application menu (D44: only macOS does that) and **never
  sets a native `action` field** (Windows menu items have no Cocoa-selector slot to route `role` through, so the
  field is carried in the generated JSON for other consumers but not read here). `gtkAccelToWindowsShortcut()`
  translates `<Primary>letter`/`<Primary><Shift>letter`/`<Shift>Fn`/bare-`Fn` accelerators to Neutralino's
  `Ctrl+Letter`-shaped `shortcut` string, display-only.
- `page-bridge.ts`: the D159 option 2 adapter, structurally identical to macOS's. `installBridge()` shims
  `window.webkit.messageHandlers.claudia` so `web/app/lib/shell-bridge.ts`'s existing `detectHandler()` finds it —
  **no change to the web app's own contract client** — answers `hello` with `welcome` directly, and turns
  `mainMenuItemClicked` into contract `action` messages. `routeMenuClick()` only special-cases `file.quit`;
  `help.about` forwards to the page like any other action on every platform, not only here, since Neutralino has
  no native About panel anywhere (D158 point 4).
- `inject-entry.ts` + `tools/build-inject.mjs`: the preload script Neutralino's `injectScript` loads, bundled by
  esbuild into one dependency-free IIFE (`apps/composes/inject/claudia-bridge.js`), with composes' title and
  generated menu JSON baked in via `--define` at build time. Unlike macOS's, does not call
  `installFileDialogBridge()` — there is no `file-dialog.ts` in this package; the WKWebView-specific bug that
  exists for is not expected on WebView2's Chromium engine (documented as a hypothesis, not yet confirmed, in this
  file's own top comment and the README's "Not verified").
- `tools/generate_menu.py` + `src/generated/menu.{composes,computes,creates}.json`: the same dev-time, GTK-free
  generator macOS already has (imports `clients/linux/src/claudia_shell_gtk/manifest.py` directly, no change
  needed for a third shell), with a `--check` drift guard and checked-in output for all three apps.
- `apps/composes/`: `icon.svg`/`icon.png` (the already-approved Linux composes glyph, rasterized) and
  `neutralino.config.json` (`tokenSecurity: one-time`, `nativeAllowList` trimmed to the four methods this client
  calls — `app.exit`, `window.setMainMenu`, `window.print`, `events.on` — per D157; `binaryVersion`/
  `clientVersion` pinned to `6.8.0`, matching macOS).
- `start-win-client.cmd` at the repository root — the Windows counterpart of `start-mac-client.sh` and
  `start-client.sh`. Runs `uv sync`, rebuilds the web frontend and the Windows client on every run (skippable with
  `CLAUDIA_SKIP_WEB_BUILD=1` / `CLAUDIA_SKIP_WINDOWS_BUILD=1`), fetches the Neutralino binary automatically with
  `npx @neutralinojs/neu update` the first time it's missing, and hands off to `node dist\launch.js <app>`
  (default `composes`) — one command instead of the README's six manual steps.
- 57 vitest tests (`identity`, `paths`, `server`, `menu`, `page-bridge`, `launch`) and 10 pytest tests
  (`generate_menu.py`); `tsc --strict` and the full build (`npm run build`) clean.
- `D158`'s `role` field ported onto `clients/linux/src/claudia_shell_gtk/manifest.py`'s shared edit/clipboard
  actions (this package's one Linux-side change): was already needed by macOS but missing from this branch's
  starting point; carried through `generate_menu.py`'s JSON for every shell even though this one does not read it.

### Not done
Packaging (an installer, `.ico`, codesigning, a Start Menu shortcut); computes and creates clients; printing as a
contract message (D158 point 2); a Windows Job Object or other fix for an orphaned server process on a hard kill
of the shell (flagged as a known open issue, matching how macOS also leaves its own equivalent gap open);
translations; single-instance behaviour; a CI job for this package (same as macOS). See the README's "Not done"
and "Not verified" sections — nothing in this version has run on a real Windows machine yet.
