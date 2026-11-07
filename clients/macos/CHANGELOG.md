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
