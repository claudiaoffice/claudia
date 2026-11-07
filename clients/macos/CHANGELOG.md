# Changelog of the macOS client

Newest first. The shell contract has its own version (`clients/contract/`); this file does not repeat it.

## [0.1.0] - unreleased

First version of the native macOS client (E5.11), for creates only, built on the user's explicit choice of D159's
loopback option ("Neutralino's window points at the document server's own loopback URL, like Linux's shell does, and
Neutralino's API is injected into that external page" — over serving Neutralino's own bundle and opening a
cross-origin WebSocket to the server).

### Added
- `identity.ts`: which macOS apps exist, their bundle id, title and server model (`de.claudiaoffice.creates` /
  `claudia_creates:SlideModel` for this first version; composes/computes listed but not yet `packaged`).
- `paths.ts`: `~/Library/Application Support/Claudia/<app>/{documents,state}` (macOS's own convention, not XDG),
  `findFrontend`/`findServerPython` with the same `CLAUDIA_WEB_DIR`/`CLAUDIA_SERVER_PYTHON` escape hatches the Linux
  client has.
- `server.ts`: `LocalServer` (spawn/checkReady/stop, SIGTERM then SIGKILL) and `freePort()`, adapted from
  `clients/linux/src/claudia_shell_gtk/server.py` for Node — no PR_SET_PDEATHSIG equivalent on macOS, and the real
  `claudia_server` package has no `--lifeline`, so there is no "the kernel cleans up if the shell is killed" guarantee
  here yet (flagged in the README's "Not verified").
- `launch.ts`: `prepareServer()` (mirrors `launch.py`'s own two `SetupProblem` messages and folder creation),
  `findNeutralinoBinary()`/`neutralinoBinaryName()` (macOS has no GTK-is-the-shell shortcut — a separate compiled
  binary has to be located), `buildShellCommand()` (`--path`/`--url`/`--enable-server`, confirmed against
  Neutralino's own "internal CLI arguments" docs), and `main()` tying server start, binary discovery and the shell
  process together.
- `menu.ts`: the shared GTK manifest (`manifest.py`'s `describe()` output, read via `generate_menu.py`) turned into
  Neutralino `WindowMenuItem[]`: `buildMainMenu()` relocates `help.about` and `file.quit` into a leading application
  menu (D44), `gtkAccelToMacShortcut()` translates `<Primary>letter` accelerators, `ROLE_SHORTCUT` gives the shared
  Edit roles (`undo:`/`cut:`/`copy:`/`paste:` — deliberately no `redo:` yet) their Cocoa shortcut.
- `page-bridge.ts`: the D159 option 2 adapter. `installBridge()` shims `window.webkit.messageHandlers.claudia` so
  `web/app/lib/shell-bridge.ts`'s existing `detectHandler()` finds it — **no change to the web app's own contract
  client** — answers `hello` with `welcome` directly, and turns `mainMenuItemClicked` into contract `action`
  messages (`routeMenuClick()`, `applyActionStates()`, `nextCheckedTarget()` are the pure, tested half; the live
  Neutralino/window wiring is the one untested part, pending a real Mac).
- `inject-entry.ts` + `tools/build-inject.mjs`: the preload script Neutralino's `injectScript` loads, bundled by
  esbuild into one dependency-free IIFE per packaged app (`apps/<app>/inject/claudia-bridge.js`), with that app's
  title and generated menu JSON baked in via `--define` at build time.
- `tools/generate_menu.py` + `src/generated/menu.{composes,computes,creates}.json`: a dev-time, GTK-free generator
  (imports `clients/linux/src/claudia_shell_gtk/manifest.py` directly) with a `--check` drift guard, checked-in output
  for all three apps.
- `apps/creates/`: `icon.svg`/`icon.png`/`icon@4x.png` (matches `AppIcon.vue`'s real creates glyph) and
  `neutralino.config.json` (`tokenSecurity: one-time`, `nativeAllowList` trimmed to the four methods this client
  calls — `app.exit`, `window.setMainMenu`, `window.print`, `events.on` — per D157; `injectGlobals`/
  `injectClientLibrary`/`injectScript` set, not yet confirmed to take effect on an externally-loaded page).
- 57 vitest tests (`identity`, `paths`, `server`, `menu`, `page-bridge`, `launch`) and 10 pytest tests
  (`generate_menu.py`); `tsc --strict`, ruff, ruff-format and mypy all clean.

### Fixed (found on the owner's first real run)
- **A crashing server was silent.** `server.ts`'s `LocalServer` piped stdout/stderr nowhere; a `ServerStartError`
  gave only a bare exit code, never why. `defaultSpawn()` now appends both (merged) to `state/server.log`, and
  `checkReady()` quotes its tail in the thrown message — the Node port of `server.py`'s own `_what_it_said()`,
  missing from the first round of this port. `launch.ts`'s `prepareServer()` points it at `state/server.log`.
- **An unhandled `'error'` event could crash the whole launcher.** A spawn the OS refuses outright (bad
  interpreter path, no execute permission) fires Node's `'error'` event, not `'exit'`; nothing listened for it, so
  it was fatal and uncaught instead of becoming a `ServerStartError` like every other start-up failure.
  `LocalServer.spawn()` now listens for it.
- **`findNeutralinoBinary()`'s default path was wrong.** It looked directly in `apps/<app>/`; `npx
  @neutralinojs/neu update` — the actual way to fetch the binary, confirmed against the E0.3 spike's own
  `run_macos.sh` — places it in `apps/<app>/bin/` instead. Fixed, and the "no binary found" message in `launch.ts`
  now names the real fetch command instead of just a path to place a file at.
- **`generate_menu.py` crashed unreadably on an old `python3`.** macOS's system `python3` can be older than
  3.12 (manifest.py's own floor); without a check, the failure surfaced as `TypeError: dataclass() got an
  unexpected keyword argument 'slots'` deep inside `manifest.py`. The script now checks `sys.version_info` first
  and refuses with a message naming the actual floor and a 3.12+ interpreter that is already there (the repo's own
  `.venv` from `uv sync`).
- `server.start()`'s `ServerStartError` was uncaught in `launch.ts`'s `main()` (a raw Node stack trace on the
  console); it is now caught and printed like every other `SetupProblem`.

### Added (after the owner's first run)
- `start-mac-client.sh` at the repository root -- the macOS counterpart of `start-client.sh`. Runs `uv sync`,
  rebuilds the web frontend and the macOS client on every run (skippable with `CLAUDIA_SKIP_WEB_BUILD=1` /
  `CLAUDIA_SKIP_MACOS_BUILD=1`), fetches the Neutralino binary automatically with `npx @neutralinojs/neu update` the
  first time it's missing, and hands off to `node dist/launch.js <app>` (default `creates`) -- one command instead
  of the README's six manual steps.

### Not done
Packaging (`.app`, `.icns`, codesigning, notarization); composes and computes clients; printing as a contract
message (D158 point 2); translations; single-instance behaviour. See the README's "Not done" and "Not verified"
sections.
