# Changelog of the macOS client

Newest first. The shell contract has its own version (`clients/contract/`); this file does not repeat it.

## [0.2.1] - unreleased

### Fixed
- **The window stayed on "Starting…" for ever** (first run on a real Mac, 2026-11-10/11). Two causes, found one after the
  other with the core's own log. (1) The core only knew its app from the environment variable `CLAUDIA_SHELL_APP`, which
  Neutralino is not documented to hand on to an extension; without it the core stopped at its first line, silently.
  (2) A wrapper script (`start-core.sh`, tried as the fix for 1) was started by Neutralino but got no tokens on stdin
  (`stdin ended before the tokens arrived`), so the core could not connect. Now the launcher puts the one shape that
  spike 5 proved into the app's `neutralino.config.json` for the run, and the default back afterwards:
  `<absolute node> [--use-system-ca] ${NL_PATH}/ext/core.mjs --app=<app> [--server=<origin>] [--debug]`
  (`core-command.ts`). Nothing is inherited and nothing is a script; the core reads its settings from its arguments, and
  falls back to the environment and then to the folder it lies in.
- The core accepted the tokens from Neutralino only if `nlPort` was a number (the spike's extension did not check the type);
  a string port made it discard what it was given and log "stdin ended before the tokens arrived". It takes both now, and
  when stdin is not usable the log names the keys and types that arrived (never the values) and how many characters.
- **A local server could not be found by the bundled core** (the core looked for the server's Python and the web build in
  `clients/macos` instead of the repository root, because the path was counted in levels from the file and the bundled
  core lies two levels deeper than the launcher). `defaultRepo` now walks up to the folder that has
  `clients/macos/package.json`; tested for `src/`, `dist/` and `apps/<app>/ext/`.
- The shell page's console says when a loaded page has not said hello after five seconds (an older web app, see the
  README) and when a native menu click had nobody to go to; both used to be silent.
- **A browser test of the whole window**, `web/e2e/macos-shell.cjs` (`npm run e2e:macos-shell` in `web/`, in CI's `e2e` job): the
  built shell page and core as a real process, a real server and the real web app in the frame; only Neutralino's client
  library is faked. It would have failed on the repository-root bug above (checked by putting the bug back).
- The core logs from its first line (`~/Library/Application Support/Claudia/<app>/state/shell.log`, or `shell.log` in that
  `Claudia` folder while it does not know its app), including its arguments, what its stdin is, crashes, Node without `WebSocket`, the tokens it got, the
  link to Neutralino and every request and answer.
- The shell page asks the core to start again every second until the core has said anything, logs which extensions
  Neutralino has loaded and connected (`extensions.getStats`), and after 20 seconds shows where to look (the log, the
  inspector) instead of "Starting…".

## [0.2.0] - unreleased

All three apps, the command line, and the server flow of the Linux client (D241–D248), on a new architecture (D251).

### Changed
- **The window is built the other way round (D251, replaces D159).** Neutralino is not given a page that it did not
  serve: spikes 1–5 (2026-11-10) showed that it then gives that page no token and never starts the client library, so
  the injected script could never use Neutralino, and the demo never had native menus (the README's earlier claim
  that "the native menu renders" was wrong: the menu seen was the web app's own). Now Neutralino shows its own
  static page (`apps/<app>/index.html`), which loads `js/neutralino.js` only (D157), sets the native menu, and shows
  the web app in a full-window frame; the two talk with `postMessage` (the shell contract). The native parts run in
  a Node *extension* that Neutralino starts and ends with the window.
- `launch.ts`: no server of its own any more and no `--url`: it finds the binary, wraps it in the minimal `.app`,
  sets the core's command in the app's config for the run (0.2.1, `core-command.ts`: the absolute `node`, `--use-system-ca`
  where Node knows the flag, `--app`, `--server`) and runs the binary with `--path`. Refuses a checkout whose path has a space, and says which command makes a missing generated file.
- `web/app/lib/shell-bridge.ts`: a framed page speaks to its parent window with `postMessage` (`detectParentSink`),
  hears only the parent window, and only when it is a page on this computer's loopback. The WebKit path of the Linux
  client is unchanged.
- `page-bridge.ts` is now `menu-actions.ts`, only its pure decisions (what a menu click means, how states change the
  menu); the live wiring is `shell-page.ts`.
- `package.json`: `bin` entries `claudia-composes`, `claudia-computes`, `claudia-creates`; Node 22+.
- `start-mac-client.sh`: takes the app and the options like `start-client.sh` (`[app] [--server URL] [--debug]`),
  `uv sync --no-dev` (the dev group's documentation tools can force a source build on a very recent Python; found for
  the Windows client), fetches Neutralino per app when binary or library is missing.

### Added
- **composes and computes** next to creates: `apps/<app>/` (config, icons from the Linux client), the identities, the
  generated menus were already there.
- **The command line** (`cli.ts`): `--server URL`, `--debug`, `--version`, `--help`; a bad address or an unknown option
  exits 2 with a message; no command asks which app to open (a window is one app).
- **The server flow of Linux**, ported: `contract.ts` (checked against the JSON schema by the tests), `servers.ts`
  (addresses and list rules), `settings.ts` (`shell.json`, shared format with Linux), `connection.ts` (reachable,
  Claudia, this window's app, certificate; a certificate nobody vouches for is refused as
  `certificate_invalid`), `connector.ts` (newest request wins), `bridge.ts` (the shell's side of the contract),
  `core.ts`/`core-protocol.ts`/`core-entry.ts`/`extension.ts` (the native core and its link to Neutralino),
  `local-server.ts` (`prepareServer`, moved out of `launch.ts`). Capabilities: `native-menu`, `actions`, `connect`, `servers`.
- `shell-page.ts`/`shell-page-entry.ts`, `tools/build-shell.mjs`, `tools/shell-page.template.html`: the shell page, built
  per app together with the core's bundle.
- Tests: 333 in 22 files, among them the contract against the schema (52 cases), the checks against real http and https
  servers (openssl certificates), and the built `ext/core.mjs` running as a real process against a fake Neutralino.

### Removed
- `inject-entry.ts`, `build-inject.mjs`, `file-dialog.ts` and the injected-script settings in the Neutralino configs:
  the injection never reached the page. The file-picker workaround cannot run in a cross-origin frame (see README,
  "Known gaps").
- `identity.ts`'s `packaged` flag.

### Fixed (twins of fixes found for the Windows client)
- The entry guard of `launch.ts` and `build-shell.mjs` compare with `pathToFileURL(process.argv[1]).href`, not a
  hand-made `file://` string, which differs for paths with spaces and made the program exit without doing anything.
- The extension link ends the process when Neutralino's socket cannot be opened: Node's WebSocket reports an error
  and no close event in that case.

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

### Fixed (the app-bundle fix worked; the file picker is a real bug, still open)

The owner's fourth run, after a clean rebuild: the app-bundle fix above is confirmed — the app-menu heading, the
Cmd+Tab switcher and Activity Monitor all now read correctly. Insert Image's file picker still does nothing, and a
clean rebuild did not change that, ruling out staleness for good.

- **A separate, real bug found while re-reading the call site: a swallowed promise rejection.**
  `installFileDialogBridge()` called `pickFiles()` with a bare `void` and no `.catch()` — any rejection (a
  permission error, the native dialog helper failing) vanished as a silent unhandled rejection, which looks
  identical to "nothing happens" without devtools open. Fixed with an explicit `.catch(console.error)`.
  `enableInspector` is now `true` in `apps/creates/neutralino.config.json` so that log (and anything else) is
  actually visible to her. Neither change fixes the underlying bug.
- **Leading theory for the underlying bug, not yet confirmed: the native dialog opens off-screen or unfocused,
  not that it fails to open at all.** `os.showOpenDialog` shows the dialog on macOS by shelling out to AppleScript
  (`osascript`) as a separate process — confirmed in the vendored `portable-file-dialogs.h` — and that file has no
  `activate`/frontmost call anywhere in it. A dialog shown this way belongs to the `osascript` process, not ours,
  and nothing asks it to come to the front. The same class of bug is independently documented in another project
  that used the same approach before dropping it (flutter_file_picker issues #1445, #1492 — see the notes file for
  links). Not confirmable without a real Mac, and not patchable from this repo even if confirmed —
  `portable-file-dialogs.h` is compiled into Neutralino's prebuilt binary, not built here.
- 79 vitest tests still (no new testable logic this round).

### Fixed (the application-menu heading fix above didn't actually work)

The owner's third run: the window title fix held, but the application-menu heading still read
`neutralino-mac_arm64`, and Insert Image's file picker still did nothing. Investigated properly this time instead
of guessing again:

- **`argv0` was the wrong mechanism.** Reading Neutralino's own macOS source
  (`api/window/window.cpp`'s `setMainMenu()`) confirms it only ever calls `NSApplication.setMainMenu:` with our
  own menu items — nothing there touches the app's own name. Outside confirmation too: a bare SDL app's menu-bar
  name did not change when `argv[0]` did ("you can't do it without putting your app in an app bundle, AFAIK",
  https://discourse.libsdl.org/t/setting-the-application-name-on-osx/31982). The heading (and the Cmd+Tab switcher,
  and Activity Monitor) read a running process's *bundle* identity — `CFBundleName`, via `NSBundle`/
  `NSRunningApplication` — which an unbundled binary simply does not have, whatever `argv0` says.
- **New `app-bundle.ts`.** `ensureAppBundle()` wraps the downloaded binary in the smallest `.app` bundle that
  gets `CFBundleName` to apply at all: `Contents/MacOS/claudia-<app>` (a copy of the downloaded binary, re-copied
  only when the source is newer — not on every launch) and `Contents/Info.plist` (rewritten every launch, cheap).
  Confirmed safe against Neutralino's own `settings.cpp`: `--path` is read as an explicit override regardless of
  where the binary itself lives, so running from inside `Contents/MacOS/` instead of `apps/<app>/bin/` directly
  changes nothing about where `neutralino.config.json` or the app's resources are found. No `.icns`, no
  codesigning, no notarization — full packaging is still "Not done"; this is only what `CFBundleName`'s
  resolution needs. The dock icon the owner already has stays exactly as it was (`modes.window.icon`, unrelated to
  a bundle's own Finder icon). `launch.ts`'s `macProcessName()`/`argv0` stays in as a harmless no-op alongside it.
- Insert Image's file picker is believed to be a stale-build symptom, not a code bug: re-verified
  `os.showOpenDialog`/`filesystem.readBinaryFile` are the exact method-name strings Neutralino's own router
  expects (`server/router.cpp`), and the `OpenDialogOptions`/`Filter` shape matches the client library's own types
  (`@neutralinojs/lib`'s `src/types/api/os.ts`) exactly. Config changes (like the window-title fix) take effect on
  the next launch with no rebuild, confirmed from `settings.cpp` reading the config file fresh every start; the
  injected bundle (`apps/<app>/inject/claudia-bridge.js`) does not — it is a build artifact of `npm run build`,
  and only updates when that actually reruns. Asked the owner to force a clean rebuild and confirm before treating
  this as still broken.
- 79 vitest tests now (6 new: `app-bundle.test.ts`).

### Fixed (found on the owner's second run, after start-up finally succeeded)

D159's core mechanic is confirmed working on her Mac: the native menu rendered, the dock showed this app's own
icon. Three further bugs surfaced once the window was actually up:

- **The application-menu heading (next to the Apple logo) read the literal binary filename,
  `neutralino-mac_arm64`.** macOS reads a running process's name for that heading (also the Cmd+Tab switcher and
  Activity Monitor) from the process itself, not from any NSMenu item `menu.ts` builds — nothing had ever set it, so
  it fell back to `argv[0]`'s basename, the downloaded binary's own name. `launch.ts`'s new `macProcessName()`
  returns `claudia <app>` (lower case — the owner's own correction, scoped to this one macOS-process-identity
  string only; `identity.ts`'s `title` stays Title Case everywhere it's shared with Linux and the web app), passed
  as `argv0` to the `child_process.spawn()` call that starts the binary.
- **The window title bar read "Claudia Creates" (capitalized); the owner wants "claudia creates" (lower case) for
  this native window.** `apps/creates/neutralino.config.json`'s `modes.window.title` is a separate, static,
  per-app string (confirmed against Neutralino's own `window` docs: nothing syncs it to the page's `document.title`
  automatically) — just needed the literal string changed, lower case, same scoping as above.
- **Insert Image's "Choose a file…" did nothing: no file picker ever appeared.** WKWebView shows no native Open
  panel for `<input type="file">` unless the host app implements the delegate method for it, which Neutralino's
  generic macOS binary does not (confirmed against
  [WebKit Bugzilla #139745](https://bugs.webkit.org/show_bug.cgi?id=139745) — a WKWebView-specific gap WebKitGTK,
  which the Linux client's view uses, does not share, which is why this was never seen there).
  `web/app/components/ImageImportDialog.vue`'s own top comment had already anticipated this ("a desktop client that
  can read the real path would pass it instead") but nothing had built that desktop client yet. New
  `file-dialog.ts`: a capture-phase click listener on every `<input type="file">` that swaps the broken native
  picker for `Neutralino.os.showOpenDialog()` + `filesystem.readBinaryFile()`, handing the result back to the input
  as an ordinary `File` via `DataTransfer` so `onFileChange` runs unchanged. `nativeAllowList` gained
  `os.showOpenDialog` and `filesystem.readBinaryFile` (D157: exact method names, nothing wider); `filesystemScopes`
  stays empty on purpose — the open dialog itself is the gate on which paths this client ever touches.
- 73 vitest tests now (16 new: `macProcessName`, `file-dialog.ts`'s pure helpers).

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
