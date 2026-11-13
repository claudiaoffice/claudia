# Changelog of the Windows client

Newest first. The shell contract has its own version (`clients/contract/`); this file does not repeat it.

## [0.2.0] - unreleased

### Changed (UX-35, UX-36)
- The menus are regenerated from the manifest: every entry has its key from the one table of all clients (D340), and the
  menus have what the web's have (File ▸ Print…, Format ▸ List ▸, Edit ▸ Image… and Chart…, Tools ▸ Names… and SQL
  Query…, View ▸ Show Grid, Edit ▸ Insert ▸). The page listens for the keys. The menu shows every key of the one table: `gtkAccelToWindowsShortcut` covers every shape it uses.

### Added
- Format ▸ Describe Object… (Ctrl+Alt+D) in claudia computes and claudia creates, by regenerating the menus from the
  Linux manifest. The page owns the dialog.

The Windows client is rebuilt on D251 (the design the macOS client proved on a real Mac, 2026-11-10) and brought to
parity with the Linux and macOS clients: all three apps, the same command line, the remote-server flow of
D241-D248. Branch `win-client-complete`. Everything here ran on Linux only; see the README's "Not verified".

### Changed
- **Architecture (D251, replaces D159).** Neutralino now shows its own static shell page
  (`apps/<app>/index.html`), the Claudia web app is framed in it, and the native parts (server checks, server
  list, settings, the local server) run in a Node extension (`ext/core.mjs`, `commandWindows` in the Neutralino
  config). The injection path (`injectScript`, `window.webkit` shim) is gone: on a page Neutralino did not serve,
  the one-time token is empty and no API call can be made.
- `web/app/lib/shell-bridge.ts` (`detectParentSink`) carried over unchanged from `macos-client-complete`, so the
  web app speaks the shell contract to its parent frame; it is the same file on both branches.
- `server.ts`: `stop()` ends the whole process tree with `taskkill /pid N /T /F` (the venv's `python.exe` is a
  launcher stub that starts the real interpreter as a child; killing the stub alone left the server running).
  Falls back to `process.kill()`. Tests never run a real `taskkill`.
- `launch.ts`: environment variables are set and removed case-insensitively (`Path` vs `PATH` on Windows);
  `NODE_OPTIONS=--use-system-ca` makes Node trust the Windows certificate store for HTTPS servers; Neutralino
  splits an extension command at spaces, so a Node path with spaces (`C:\Program Files\nodejs\node.exe`) is
  replaced by its 8.3 short name for the run, with a plain `node` fallback and a note on the console. The
  Neutralino config is changed only for the run and restored afterwards.
- `paths.ts`: `configDir`, and a walk up from the bundled core to the repository root (`findRepo`/`defaultRepo`),
  so the core finds the server's Python and the web build.
- `.gitignore`, CI (`windows-client` job builds the shell; the `e2e` job runs `e2e:windows-shell`).

### Added
- Composes, computes and creates (`apps/<app>/neutralino.config.json`, icons); a window is one app (D242).
- Command line, same as Linux and macOS: `claudia-<app> [--server URL] [--debug]`, `node dist\launch.js <app> ...`,
  `bin/<app>.mjs` shims, and `start-win-client.cmd [composes|computes|creates] [--server URL] [--debug]`.
- The server flow of the Linux client: `contract.ts` (all eight message types, checked against the JSON schema),
  `servers.ts`, `settings.ts` (`shell.json`, same format as Linux), `connection.ts`, `connector.ts`, `bridge.ts`,
  `core.ts`, `core-entry.ts`, `core-command.ts`, `core-protocol.ts`, `extension.ts`, `shell-page.ts`,
  `shell-page-entry.ts`, `tools/build-shell.mjs`, `tools/shell-page.template.html`.
- `web/e2e/windows-shell.cjs` (`npm run e2e:windows-shell`): the real shell page, the real core process, the real
  local server and the real web app in Chromium, with only Neutralino's client object faked; per app, plus `--server`.
- Tests: 335 vitest tests (was 63).

### Removed
- `page-bridge.ts`, `inject-entry.ts`, `tools/build-inject.mjs` and their tests (D159 path). This also retires the
  three Windows-only fixes of the old `[unreleased]` section for `build-inject.mjs`; the entry guard
  (`pathToFileURL`) and `windowsHide` fixes live on in the new code.

## [0.1.1] - unreleased (fixes found on real runs; carried into 0.2.0)

### Changed
- `src/generated/menu.*.json` regenerated: Format starts with **Apply Style…** (`format.apply-style`, D301), which
  opens the page's style popover in its apply mode, as in the GTK shell.

### Fixed
- `tools/build-inject.mjs`: `npm run build:inject` failed on a real Windows machine with
  `Error [ERR_UNSUPPORTED_ESM_URL_SCHEME] ... Received protocol 'c:'`, found on the owner's first real run
  (Windows VM, Git Bash, 2026-11-09). A dynamic `import()` specifier has to be a URL; the script passed a bare
  `node:path`-joined filesystem path, which Node tolerates on POSIX (no "scheme:" prefix to confuse it with) but
  not on Windows, where an absolute path's drive letter ("C:\...") parses as an unsupported URL scheme. Fixed with
  `pathToFileURL(identityPath).href`, Node's own documented fix, identical on every OS. New regression test
  (`tests/build-inject.test.ts`, 3 tests) pins down the exact scheme-parsing property that broke, independent of
  which OS actually runs it. The identical bug is present, unexercised, in `clients/macos/tools/build-inject.mjs`
  (POSIX absolute paths never trigger it) — worth the same one-line fix there.
- `start-win-client.cmd`: `uv sync` (no flags) failed building `pyyaml` from source on a second real Windows run
  (2026-11-09) with `error: Microsoft Visual C++ 14.0 or greater is required`. `pyyaml` is not a runtime
  dependency of anything this client needs — it arrives only through the root `dev` dependency group's
  `myst-parser` (Sphinx docs tooling), which `uv sync` installs by default alongside the actual server/client
  packages. On a very recent Python (3.15) with no published Windows wheel yet, that group forces a source build
  of `pyyaml`'s optional C extension, needing a C toolchain that is no part of this client's own requirements.
  Fixed: `uv sync --quiet --no-dev` (confirmed directly: `uv tree --no-dev` shows no `pyyaml`/`myst-parser`/
  `sphinx` at all, while the default tree lists all three under `(group: dev)`). `start-client.sh` and
  `start-mac-client.sh` call plain `uv sync --quiet` too and carry the same latent risk, just not yet hit by
  either OS's own Python/compiler situation — worth the same flag there.
- `src/launch.ts`: the module's own `if (import.meta.url === ...) main(...)` entry guard silently evaluated
  false on every real Windows run, so `node dist\launch.js composes` built and exited with no output and no
  window at all — found on a third real run (2026-11-09), after the first two fixes let the build and `uv sync`
  steps both succeed. The guard compared `import.meta.url` (a well-formed URL Node computes correctly) against
  `` `file://${process.argv[1]}` `` (a bare string template) — on Windows, `process.argv[1]` is a backslashed,
  drive-lettered path, and prepending `"file://"` to it produces a malformed URL that can never equal
  `import.meta.url`'s real, forward-slashed form. This happened to work on POSIX by coincidence (an absolute
  path already starts with `/`, so `"file://" + "/x"` is already the valid `"file:///x"`), which is exactly why
  it shipped broken and untested for Windows. Fixed with `pathToFileURL(process.argv[1] ?? '').href`, the same
  Node-documented fix as the first two bugs this real-run cycle found. Two new regression tests in
  `tests/launch.test.ts` pin down the comparison's own correctness without running `main()` for real (which
  spawns a server and, if found, a Neutralino binary — real side effects a unit test should not have). 62 vitest
  tests now, up from 60. **The identical bug exists, unexercised, in `clients/macos/src/launch.ts`** (POSIX
  argv[1] never triggers it) — worth the same one-line fix there, same as the other two Windows-only bugs this
  real-run cycle found and macOS's own `build-inject.mjs` quietly shares.
- `src/server.ts`: `defaultSpawn()` started the server with `detached: true` but no `windowsHide`, so a fourth
  real Windows run (2026-11-09) saw the Python server pop up its own, separate, empty console window — nothing
  was ever going to appear in it, since its stdout/stderr are already redirected to `logPath`, so the window was
  only ever a confusing distraction. `windowsHide: true` is Node's own documented flag for exactly this (a no-op
  on every other OS); added alongside `detached: true`, not instead of it — they solve two different halves of
  the same Windows gap (this module's own top comment). New regression test in `tests/server.test.ts` spies on
  `node:child_process`'s `spawn` (via `vi.mock`/`vi.hoisted`, wrapping the real implementation) to check the
  actual options object passed, since `windowsHide`, unlike `detached`, leaves no trace on the `ChildProcess`
  object afterwards for a test to read back. 63 vitest tests now, up from 62.

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
