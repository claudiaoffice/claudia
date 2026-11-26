# Changelog of the macOS and Windows client

Newest first. The shell contract has its own version (`clients/contract/`); this file does not repeat it. Until D660 the
two systems had a package each, `clients/macos` and `clients/windows`; their histories follow the first entry.

## [0.3.0] - unreleased

### Added (SEC-27): where a picked file is
- The core's `file_result` `picked` carries `path`, the chosen file's full path, and the shell page hands it to the
  page (contract version 1, an optional field), for Insert ▸ Image's "Don't save the path".

### Added (E8.5, D1622, D1624): Shared on this computer
- The computer's claudia service is listed after her private place as a `shared` entry, found by its installer's marker
  (`shared-service.ts`; `HostPlatform.sharedServiceFile`: `/Library/Application Support/Claudia/service.json`,
  `%ProgramData%\Claudia\service.json`). Only a name a person gives it is remembered; opening it does not remember it.
- Its page gets the service's setup code when she may read it, else `ask_administrator` in `welcome`
  (`Core.show`, `Bridge` option `setup`, which replaces `setupCode`).

### Changed (E8.5, D1620, D1621, D1623; CODE-99, CODE-100): her private server
- The desktop's one shared server is now a person's private server, "Private on this computer":
  `desktop-server.ts`/`DesktopServer` became `private-server.ts`/`PrivateServer`. It is on a port of her account
  (20000–29999, `private-port.ts`; `CLAUDIA_SERVER_PORT` still takes its place), started with `--owner-key-file`
  (`owner-key.ts`), and used only when it proves to be hers. While something else holds her port it goes to the next
  free port of her range, written down as `{"instead": N}` in `desktop-server.json` (older files are not read).
- `SERVER_PORT`, `readPort`, `writePort` and `freePort` are gone. The shell's own label for the entry is "Private on
  this computer"; the page names it in her language.

### Added (SEC-12, D1373): the setup code of the desktop's own server
- The core sends its own server's setup code with `show` (`setupCode`, read in the state folder whenever it shows that
  server); the shell page hands it to the page in `welcome` (`setup_code`), never for another server.
  `DesktopServer.setupCode`, `readSetupCode`; `BridgeOptions.setupCode`; `contract.welcome({ setupCode })`.

### Added (E9.32): the table entries of composes
- The generated menu of Claudia Composes has Insert ▸ Table… and Edit ▸ Row ▸, Column ▸, Sort ▸, Merge Cells, Split Cell and Table Options…, with their Ctrl+… shortcuts.

### Added (D740, D741): what the Windows installer needs
- `CLAUDIA_SERVER_EXE` starts a self-contained `claudia-server` program instead of Python (`findServerProgram`); it wins over `CLAUDIA_SERVER_PYTHON`.
- Packaged mode: a `packaged.json` next to `package.json` points the client at the installed web frontend and server, and
  the window runs from a copy of the app folder in `%LOCALAPPDATA%\Claudia\run\<app>`, so an installation in `Program Files` can stay read-only.
- A checkout in a folder with a space on Windows runs from the folder's 8.3 short name, or says how to move it.

### Changed (D660, CODE-14): one package for macOS and Windows
- `clients/neutralino` replaces `clients/macos` and `clients/windows`. Everything is shared but `src/platform/`, which
  holds what is the operating system's own: the folders (`~/Library/Application Support/Claudia`,
  `%LOCALAPPDATA%\Claudia`), where `uv sync` puts the server's Python, Neutralino's binary, the `.app` around it on a Mac,
  the dialogs (osascript, PowerShell), ending a server (signals to its process group, `taskkill /T`), the 8.3 short name
  of node's path on Windows, the menu (application menu and Cocoa roles on a Mac, Ctrl+… shortcuts on Windows) and the
  words a person reads.
- `npm run build:macos` and `npm run build:windows` build the bundles for one platform; `npm run build` for the computer
  it runs on. A bundle knows its platform (`CLAUDIA_PLATFORM`), so a Windows build behaves like Windows wherever it runs.
  The launcher and the tests ask the operating system. Both platforms' code is tested on every runner.
- One `neutralino.config.json` per app, with the core's command for both systems (`commandDarwin`, `commandWindows`;
  the launcher sets the one of the system it runs on). The window is closed through the page on Windows too
  (`exitProcessOnClose: false`, the page ends the app on `windowClose`, as on a Mac since D506): not yet tried on
  Windows.
- On a Mac, the path of node with a space in it no longer stops the launcher: as on Windows, it starts the core as a
  plain `node` from PATH (the launcher put node's folder first) and says so.
- A name that is no app is refused with "there is no Claudia app called '…'".
- `bin/` (the `claudia-<app>` commands) is part of the package on both systems; the macOS package named it in
  `package.json` without having it.
- `generate_menu.py` is one script and writes the menus once; `npm run generate-menu` and `check-menu` run it with
  `uv run --no-project python`.

### Removed (CODE-40)
- `apps/creates/inject/claudia-bridge.js`, a build of the superseded page-bridge adapter (D159) that nothing used.

## History of the macOS client (clients/macos)

### [0.2.1] - unreleased

#### Fixed (CODE-26, D506): closing a window no longer crashes the app
- The close button ended every app with a crash (Neutralino 6.8.0 traps in `window::_close()` when the window closes
  itself). `exitProcessOnClose` is `false` in the three `neutralino.config.json`; the shell page hears `windowClose` and
  ends the app with `app.exit`, as Quit does.
#### Added (D1024)
- Format ▸ Rotate ▸ Rotate Right 90° (Ctrl+Alt+.), Rotate Left 90° (Ctrl+Alt+,) and Rotate By… (Ctrl+Alt+Shift+Z) in creates. Ctrl+Alt+Z stays Replay History's, so Rotate By… takes the Shift.
- The menus of the macOS and Windows clients are generated again from the manifest: they had not been since the Insert menu was added.

#### Added (D552, E6.24)
- Edit ▸ Rename Sheet… in computes and Edit ▸ Rename Slide… in creates (Ctrl+Shift+F11), after New Sheet and New Slide.
#### Added (D627): Tools ▸ Pivot Table… and the entries that work on one
- The generated Computes menu has Pivot Table…, Pivot Fields, Value Field Settings…, Show Pivot Table as SQL… and Delete Pivot Table…, with the keys of the shared manifest.

#### Changed (D504): the local server is on port 8765
- The shared local server listens on 8765, the port of `./start.sh`; a Claudia server of the same version already there
  is used, whoever started it. Another port only when something else holds 8765 (logged), or with
  `CLAUDIA_SERVER_PORT`. The e2e script gives each window a free port of its own.

#### Changed (D445, D444, D434): the three apps share one local server, as on Windows
- The core no longer starts a server of its own app (`--model`, random port) and stops it with the window. The first
  window finds or starts the one server of the suite (`desktop-server.ts`, the Windows client's, unchanged but for the
  name of Activity Monitor): all three apps, one folder of documents and one of state
  (`~/Library/Application Support/Claudia/documents` and `…/state`), the port remembered in `state/desktop-server.json`,
  `--exit-when-idle 600`. Closing a window only lets go of its presence connection; the server stops by itself ten
  minutes after nothing is connected. Documents of the old per-app folders are not moved (D437).
- `welcome` carries the window's app (D444): on the shared server the front page shows this app's documents only.
- The web inspector is off in the three `neutralino.config.json`, on for a `--debug` run only.

#### Added (D501, D502, D503)
- Files through the Mac's own panels (shell contract capability `files`): Open a File… and Insert Image show
  NSOpenPanel, in front of the window (the panel did not come up at all before); Export…, Download and Download PDF
  show NSSavePanel and say where the file went. The core shows the panels (`dialogs.ts`, through `osascript`) and reads
  and writes the files (`files.ts`); the shell page passes the pieces on.
- Print… in the print preview opens the pages in the Mac's PDF viewer, which prints them.
- A native menu action gives the frame the keyboard focus first, so that what the page does is seen (File ▸ Open… on
  the front page puts the cursor into the search field).

#### Fixed
- Two windows starting at once could pick two ports: the port file is now written whole and linked into place.

#### Fixed
- The end-to-end script of the macOS shell (`web/e2e/macos-shell.cjs`) reads the document's native menu (the latest one
  the shell was given), not the front page's short one that comes first, and checks that the front page has the short one.
- `src/generated/menu.computes.json` is regenerated: File ▸ Print… (Cmd+P) is in the menus of Claudia Computes, as in
  the other two apps.

#### Changed (UX-35, UX-36)
- The menus are regenerated from the manifest: every entry has its key from the one table of all clients (D360), and the
  menus have what the web's have (File ▸ Print…, Format ▸ List ▸, Edit ▸ Image… and Chart…, Tools ▸ Names… and SQL
  Query…, View ▸ Show Grid, Edit ▸ Insert ▸). The page listens for the keys. Keys of the shape Cmd+letter are claimed by the menu (Cmd+O, S, P, F, M, Q); the others are shown by the page's own menus only. Cmd+M is macOS's Minimize and Cmd+Option+H its Hide Others: a Mac-specific variant of the table is still to come (D360).

#### Added
- Format ▸ Describe Object… (Cmd+Option+D) in claudia computes and claudia creates, by regenerating the menus from the
  Linux manifest. The page owns the dialog.

#### Changed
- `src/generated/menu.creates.json` regenerated (E10.2, D344): View has **Present from the First Slide** (`F5`,
  `Ctrl+Alt+P`), **Present from This Slide** (`Shift+F5`, `Ctrl+Alt+Shift+H`) and **Speaker Notes** (checkable,
  `Ctrl+Alt+V`); Edit has **Plan the Time of This Slide…** (`Ctrl+Alt+Shift+T`). All are page actions: the page does the work,
  the shell needs nothing new. F5 alone is not enough on a Mac (a system key there), hence the second chord.

#### Fixed
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

### [0.2.0] - unreleased

All three apps, the command line, and the server flow of the Linux client (D241–D248), on a new architecture (D251).

#### Changed
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

#### Added
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

#### Removed
- `inject-entry.ts`, `build-inject.mjs`, `file-dialog.ts` and the injected-script settings in the Neutralino configs:
  the injection never reached the page. The file-picker workaround cannot run in a cross-origin frame (see README,
  "Known gaps").
- `identity.ts`'s `packaged` flag.

#### Fixed (twins of fixes found for the Windows client)
- The entry guard of `launch.ts` and `build-shell.mjs` compare with `pathToFileURL(process.argv[1]).href`, not a
  hand-made `file://` string, which differs for paths with spaces and made the program exit without doing anything.
- The extension link ends the process when Neutralino's socket cannot be opened: Node's WebSocket reports an error
  and no close event in that case.

### [0.1.0] - unreleased

First version of the native macOS client (E5.11), for creates only, built on the user's explicit choice of D159's
loopback option ("Neutralino's window points at the document server's own loopback URL, like Linux's shell does, and
Neutralino's API is injected into that external page" — over serving Neutralino's own bundle and opening a
cross-origin WebSocket to the server).

#### Added
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

#### Fixed (found on the owner's first real run)
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

#### Fixed (the app-bundle fix worked; the file picker is a real bug, still open)

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

#### Fixed (the application-menu heading fix above didn't actually work)

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

#### Fixed (found on the owner's second run, after start-up finally succeeded)

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

#### Added (after the owner's first run)
- `start-mac-client.sh` at the repository root -- the macOS counterpart of `start-client.sh`. Runs `uv sync`,
  rebuilds the web frontend and the macOS client on every run (skippable with `CLAUDIA_SKIP_WEB_BUILD=1` /
  `CLAUDIA_SKIP_MACOS_BUILD=1`), fetches the Neutralino binary automatically with `npx @neutralinojs/neu update` the
  first time it's missing, and hands off to `node dist/launch.js <app>` (default `creates`) -- one command instead
  of the README's six manual steps.

#### Not done
Packaging (`.app`, `.icns`, codesigning, notarization); composes and computes clients; printing as a contract
message (D158 point 2); translations; single-instance behaviour. See the README's "Not done" and "Not verified"
sections.

## History of the Windows client (clients/windows)

### [0.2.0] - unreleased

#### Added (D1024)
- Format ▸ Rotate ▸ Rotate Right 90° (Ctrl+Alt+.), Rotate Left 90° (Ctrl+Alt+,) and Rotate By… (Ctrl+Alt+Shift+Z) in creates. Ctrl+Alt+Z stays Replay History's, so Rotate By… takes the Shift.
- The menus of the macOS and Windows clients are generated again from the manifest: they had not been since the Insert menu was added.

#### Added (D552, E6.24)
- Edit ▸ Rename Sheet… in computes and Edit ▸ Rename Slide… in creates (Ctrl+Shift+F11), after New Sheet and New Slide.
#### Added (D627): Tools ▸ Pivot Table… and the entries that work on one
- The generated Computes menu has Pivot Table…, Pivot Fields, Value Field Settings…, Show Pivot Table as SQL… and Delete Pivot Table…, with the keys of the shared manifest.

#### Changed (D504): the local server is on port 8765
- The shared local server listens on 8765, the port of `./start.sh`; a Claudia server of the same version already there
  is used, whoever started it. Another port only when something else holds 8765 (logged), or with
  `CLAUDIA_SERVER_PORT`. The e2e script gives each window a free port of its own.

#### Added (D501, D502, D503)
- Files through Windows' own dialogs (shell contract capability `files`): Open a File… and Insert Image show the Open
  dialog, from the native menu too; Export…, Download and Download PDF show the Save dialog and say where the file went,
  instead of WebView2 putting it into Downloads without a word. The core shows the dialogs (`dialogs.ts`, Windows Forms
  through PowerShell, in front of the window) and reads and writes the files (`files.ts`); the shell page passes the
  pieces on. Not run on Windows yet.
- Print… in the print preview opens the pages in Windows' application for PDFs, which prints them.
- A native menu action gives the frame the keyboard focus first, so that what the page does is seen.

#### Fixed
- Two windows starting at once could pick two ports: the port file is now written whole and linked into place.

#### Fixed (CI on Windows)
- The web app's front page now takes part in the shell handshake when it runs in a Neutralino window (a frame of the
  shell page), not only under the macOS WebKit handler. Before, the window's app was unknown there, so the front
  page asked "which kind of document?" in a window of one app, and had no list of the shell's servers.
- The end-to-end script `web/e2e/windows-shell.cjs` expects what D445 made of the window's end: the shared server is
  left running to stop by itself, not stopped with the window; and the front page's short native menu comes before
  the document's.
- The launcher's rewrite of `neutralino.config.json` (the core's command, the inspector) keeps the line ends the file
  has: a checkout with CRLF came back with LF, which Git shows as a change of every line.
- The core's log says `stdin is a pipe, as far as Windows says`: Windows' `fstat` shows the pipe of a child's stdin
  as neither a FIFO nor a socket, so the log used to say "something else".
- `src/generated/menu.computes.json` is regenerated: File ▸ Print… (Ctrl+P) is in the menus of Claudia Computes.

#### Changed (D445, D444, D434): the three apps share one local server
- **One server for all three windows.** The core no longer starts one server per app on a random port with
  `--model`. The first window to start launches `python -m claudia_server --apps all` (the default) with
  `--exit-when-idle 600`, one documents folder (`%LOCALAPPDATA%\Claudia\documents`, one subfolder per app) and one
  state folder (`%LOCALAPPDATA%\Claudia\state`: `server.log`, `desktop-server.json`). The port is chosen once and
  remembered in `desktop-server.json`; every later window finds the server by `/api/health` and starts nothing.
  Windows opened together settle it with the folder lock (D435): the one that loses waits for the winner. A server
  that is not Claudia's (or serves other apps, or another version) is reported, never taken over; a remembered port
  that something else has taken is replaced. New: `src/desktop-server.ts`; `local-server.ts` and `core.ts` use it.
- **Closing a window no longer stops the server, and no server is left behind.** Each window keeps a socket on
  `/api/presence` open (D434); the server leaves by itself ten minutes after the last window is gone. If the server
  is gone while a window is open (idle exit, someone ended it), the shell starts it again on the same port.
- **The window shows its own app only (D444).** The `welcome` message carries `app`; the contract's field is optional.
- `server.ts`: the server is started detached and `unref`'d so it can outlive the window that began it. A start
  that fails quotes only what the server wrote since *this* start (`server.log` is shared and appended to), not the
  tail of an earlier run. `ServerStartError.exited` tells a lost race from a server that never answered.

#### Fixed
- **The web inspector (DevTools) opened with every window.** `enableInspector` was `true` in the three Neutralino
  configs, and Neutralino opens the DevTools window by itself when it is on. It is now `false`; `--debug` turns it on
  for that run only (`setInspector`, restored when the launcher ends, like the core's command). The shell page's
  time-out message points to `--debug` instead of "right-click, Inspect".
- A second start no longer shows the start-up notes of an earlier run in the window (see the log quoting above).
  The empty start page after a restart was most likely a leftover per-app server holding the folder lock (D435); a
  server from an older build may still run on a machine that used it: end the `python.exe` processes of Claudia once
  in the Task Manager. **Not run on Windows**, see the README's "Not verified".

#### Changed (UX-35, UX-36)
- The menus are regenerated from the manifest: every entry has its key from the one table of all clients (D360), and the
  menus have what the web's have (File ▸ Print…, Format ▸ List ▸, Edit ▸ Image… and Chart…, Tools ▸ Names… and SQL
  Query…, View ▸ Show Grid, Edit ▸ Insert ▸). The page listens for the keys. The menu shows every key of the one table: `gtkAccelToWindowsShortcut` covers every shape it uses.

#### Added
- Format ▸ Describe Object… (Ctrl+Alt+D) in claudia computes and claudia creates, by regenerating the menus from the
  Linux manifest. The page owns the dialog.

The Windows client is rebuilt on D251 (the design the macOS client proved on a real Mac, 2026-11-10) and brought to
parity with the Linux and macOS clients: all three apps, the same command line, the remote-server flow of
D241-D248. Branch `win-client-complete`. Everything here ran on Linux only; see the README's "Not verified".

#### Changed
- `src/generated/menu.creates.json` regenerated (E10.2, D344): View has **Present from the First Slide** (`F5`,
  `Ctrl+Alt+P`), **Present from This Slide** (`Shift+F5`, `Ctrl+Alt+Shift+H`) and **Speaker Notes** (checkable,
  `Ctrl+Alt+V`); Edit has **Plan the Time of This Slide…** (`Ctrl+Alt+Shift+T`). All are page actions: the page does the work,
  the shell needs nothing new. F5 alone is not enough on a Mac (a system key there), hence the second chord.

#### Changed
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

#### Added
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

#### Removed
- `page-bridge.ts`, `inject-entry.ts`, `tools/build-inject.mjs` and their tests (D159 path). This also retires the
  three Windows-only fixes of the old `[unreleased]` section for `build-inject.mjs`; the entry guard
  (`pathToFileURL`) and `windowsHide` fixes live on in the new code.

### [0.1.1] - unreleased (fixes found on real runs; carried into 0.2.0)

#### Changed
- `src/generated/menu.*.json` regenerated: Format starts with **Apply Style…** (`format.apply-style`, D301), which
  opens the page's style popover in its apply mode, as in the GTK shell.

#### Fixed
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

### [0.1.0] - unreleased

First version of the native Windows client (E5.11), for composes only, carrying over D159's loopback option
("Neutralino's window points at the document server's own loopback URL, like Linux's shell does, and Neutralino's
API is injected into that external page") rather than asking the transport question again for a second platform —
nothing in the spike or the macOS build found an OS split in that answer.

#### Added
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

#### Not done
Packaging (an installer, `.ico`, codesigning, a Start Menu shortcut); computes and creates clients; printing as a
contract message (D158 point 2); a Windows Job Object or other fix for an orphaned server process on a hard kill
of the shell (flagged as a known open issue, matching how macOS also leaves its own equivalent gap open);
translations; single-instance behaviour; a CI job for this package (same as macOS). See the README's "Not done"
and "Not verified" sections — nothing in this version has run on a real Windows machine yet.
