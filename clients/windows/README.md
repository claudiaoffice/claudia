# Claudia for Windows (claudia-shell-windows)

The native client of Claudia for Windows: a thin Neutralino shell around the one web frontend (D42–D44), the same
discipline the Linux (`clients/linux/`) and macOS (`clients/macos/`) clients follow for GTK and Cocoa respectively.
Today it contains **Claudia Composes**; computes and creates follow the same way Linux's did (one more entry in
`identity.ts`, one more `apps/<app>/`).

**This has now run on a real Windows machine four times** (owner, same Windows VM, Git Bash, 2026-11-09) — far
enough to find and fix a real bug each time: first in `npm run build:inject`, then in `start-win-client.cmd`'s
own `uv sync` step, then in `launch.ts`'s own entry-point guard (the build and `uv sync` could both succeed and
`node dist\launch.js composes` would still just exit with no output and no window at all), then a cosmetic but
confusing `windowsHide` gap in how the server itself is spawned (see "First real run" through "Fourth real run"
in `claudiaoffice-log/notes/e5-11-windows-client.md` for the detail). The fourth run got further than any
before it — the server process now actually starts — but did not yet get all the way to the server answering
its own health check in time; see that run's own section for what is and is not yet understood about that. No
run has yet reached the point where the Neutralino binary itself is actually spawned. D159's core mechanic
(`window.Neutralino` existing and working on an externally-loaded loopback page) was confirmed on macOS on the
owner's own Mac, and nothing in the spike or in Neutralino's own documentation suggests Windows differs —
`injectGlobals`/`injectClientLibrary`/`injectScript` are Neutralino's own cross-platform settings, not
OS-specific ones — but on Windows that is still an expectation, not a confirmed result. Everything below "Not
verified" is this client's best-effort answer, pending a run that gets further than these four did.

```
clients/
  contract/            the shell contract: JSON schema, versioned, shared by every shell (see its README)
  windows/
    src/
      identity.ts       which app, its bundle id, title, server model          (plain Node)
      paths.ts           %LOCALAPPDATA%\Claudia, frontend/python lookup       (plain Node)
      server.ts          start, wait for and stop the local server, freePort() (plain Node)
      menu.ts            the shared GTK manifest -> Neutralino WindowMenuItem  (plain TS)
      page-bridge.ts      D159 option 2: shims window.webkit.messageHandlers   (plain TS; a few real Neutralino calls in installBridge())
      inject-entry.ts    the file Neutralino's injectScript actually loads     (bundled, not run directly)
      launch.ts          prepare the server, find the binary, start both       (Node + child_process)
      generated/         menu.<app>.json, checked in, generated from manifest.py
    tools/
      generate_menu.py   imports clients/linux's manifest.py (no GTK) and writes generated/menu.<app>.json
      build-inject.mjs   esbuild: bundles inject-entry.ts into apps/<app>/inject/claudia-bridge.js
    apps/composes/
      neutralino.config.json, icon.svg/png, inject/claudia-bridge.js (built by npm run build, not checked in),
      bin/neutralino-win_x64.exe (downloaded by npx @neutralinojs/neu update, not checked in either)
    tests/
```

Unlike macOS, there is **no `app-bundle.ts`** and **no `file-dialog.ts`** here — see "How it works" for why both
are Windows-specific non-problems rather than ports that were skipped.

## Running it from a checkout

```
uv sync --no-dev                           # the server's Python 3.14 environment: .venv -- --no-dev skips the
                                            # repo's own docs/lint/test tooling (sphinx, pytest, ruff...), which
                                            # this client needs none of and which can force an unnecessary source
                                            # build of a C extension on a Python this new (see "Not verified" 5)
(cd web && npm ci && npm run build)        # the web frontend: web\.output\public
cd clients\windows && npm ci
npm run generate-menu                      # regenerate src/generated/menu.*.json from the shared manifest --
                                            # needs Python 3.12+ on PATH as `python` (see note below)
npm run build                              # tsc, then bundles apps/composes/inject/claudia-bridge.js
(cd apps\composes && npx @neutralinojs/neu update)   # downloads the pinned binary into apps/composes/bin/
node dist\launch.js composes
```

Or, from the repository root, `start-win-client.cmd` does all of the above for you in one go (including fetching
the Neutralino binary if it's missing) — see its own comments for the `CLAUDIA_SKIP_WEB_BUILD`/
`CLAUDIA_SKIP_WINDOWS_BUILD` escape hatches, and `start-mac-client.sh`/`start-client.sh` for the macOS/Linux
equivalents.

**`npm run generate-menu` needs a `python` that is 3.12 or newer**, because it imports the shared manifest
(`clients/linux/src/claudia_shell_gtk/manifest.py`), which uses `@dataclass(slots=True)`. The interpreter on PATH
on a fresh Windows install is frequently missing entirely (only a Windows Store stub) or older than 3.12 — this
script checks the version itself first and refuses with a clear message instead of the confusing
`TypeError: dataclass() got an unexpected keyword argument 'slots'` that would otherwise surface many frames deep
inside `manifest.py`, naming the repository's own `uv sync` environment (`..\..\.venv\Scripts\python.exe`) as a
3.12+ interpreter that is already there. This step is not strictly required to build or run the client — the
checked-in `src/generated/menu.*.json` is used either way — it only needs to be run again after an edit to the
shared manifest.

**The Neutralino binary is not checked into the repository** (D157: pin it to the same version as the client
library, 6.8.0 today). `npx @neutralinojs/neu update`, run from inside `apps/<app>/` (where that app's own
`neutralino.config.json` lives), reads `cli.binaryVersion` from it and downloads the matching binary into a `bin/`
subdirectory it creates there — `apps/composes/bin/neutralino-win_x64.exe`, the only binary Neutralino 6.8.0
publishes for Windows today (no `win_arm64`, so unlike macOS's `findNeutralinoBinary`, there is no architecture to
branch on). `launch.ts` looks there by default; if a binary already exists somewhere else, point
`CLAUDIA_NEUTRALINO_BIN` at it instead.

Documents are kept in `%LOCALAPPDATA%\Claudia\composes\documents` and the server's state — including
**`server.log`**, the first place to look if `node dist\launch.js composes` reports `ServerStartError` — in the
sibling `state\` folder. There is no installer yet (icon assets exist as PNG; an `.ico`, a signed installer and a
Start Menu shortcut are not done — see "Not done").

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv\Scripts\python.exe` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web\.output\public` of the checkout (nothing ships a packaged copy yet). If set, it is the only candidate: a wrong path is reported, not replaced. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `bin\neutralino-win_x64.exe` under `apps/<app>/`, where `npx @neutralinojs/neu update` places it; not checked into the repo. |

If the server itself fails to start, `launch.ts` quotes the end of `server.log` in the error message instead of
just the bare exit code — a missing `claudia_server` package, a bad `--model`, or anything else the server printed
on its way out shows up directly on the console.

## How it works

* **The server, started by this launcher, not by Neutralino.** `launch.ts` spawns `<server python> -m
  claudia_server --model claudia_composes:TextModel --host 127.0.0.1 --port <free port> --no-tls --web <frontend>
  ...` itself (plain `node:child_process`, mirroring `server.py`/`launch.py` on Linux and `launch.ts` on macOS) and
  waits for `/api/health`, **before** the Neutralino binary is started at all — the server's address has to exist
  first, because it becomes the `--url` the shell is pointed at.
* **D159 option 2: the window loads that address, not anything Neutralino ships.** The binary runs as
  `claudia-composes --path=apps/composes --url=http://127.0.0.1:<port> --enable-server=true`. `--path` keeps
  `neutralino.config.json` (and its `injectGlobals`/`injectClientLibrary`/`injectScript` settings) in effect;
  `--url` overrides what the window actually shows. `--enable-server=true` is Neutralino's own documented
  requirement for loading a remote/external URL — it is the native-API/WebSocket channel the injected script
  depends on. Carried over from macOS's own explicit choice of this option (the owner made that call once, for
  "a Neutralino shell", not separately per OS — nothing in the spike or the build found a platform split in the
  transport question).
* **The injected script (`inject-entry.ts`, bundled to `apps/composes/inject/claudia-bridge.js`) is the whole
  adapter.** It shims `window.webkit.messageHandlers.claudia.postMessage` to look exactly like the WebKitGTK
  handler `web/app/lib/shell-bridge.ts`'s own `detectHandler()` already looks for — so **the web app needs zero
  changes** for a third shell, the same way D121 put the contract client directly in the page for the first one.
  It answers `hello` with `welcome` itself (there is no separate native shell process to round-trip to: this
  script *is* the shell, running inside the page), builds the native menu from the generated manifest JSON, and
  turns `mainMenuItemClicked` into contract `action` messages. `build-inject.mjs` reaches `identity.ts`'s compiled
  output with `pathToFileURL(...).href`, not a bare path — a dynamic `import()` specifier has to be a URL, and a
  raw Windows absolute path ("C:\...") parses as one with an unsupported "c:" scheme instead
  (`ERR_UNSUPPORTED_ESM_URL_SCHEME`), the first bug this client's first real run on Windows found (2026-11-09).
* **`uv sync` runs with `--no-dev`.** The root `dev` dependency group (Sphinx, `pytest`, `mypy`, `ruff`,
  `vulture`...) is for working on the repository itself, not for running a client to test it, and installing it
  by default is what the second real run's bug actually was: `myst-parser` (in `dev`) depends on `pyyaml`, which
  has no prebuilt Windows wheel for every Python version and tries to compile a C extension that needs a
  compiler nothing here requires otherwise. `--no-dev` sidesteps the whole group — none of it is a dependency of
  `claudia_server` or any client.
* **`launch.ts`'s own entry-point guard, fixed with `pathToFileURL`.** `if (import.meta.url === ...) main(...)`
  at the bottom of `launch.ts` is what makes `node dist\launch.js composes` actually do anything when run
  directly rather than imported. It used to compare against a bare `` `file://${process.argv[1]}` `` string
  template, which is a well-formed URL only on POSIX (an absolute path already starts with `/`); on Windows,
  `process.argv[1]` is backslashed and drive-lettered, so the template was malformed and the comparison was
  always false — `main()` was simply never called, with no error and no output of any kind, the third bug this
  client's real Windows runs found (2026-11-09). Fixed the same way as the other two: `pathToFileURL(...).href`.
* **`defaultSpawn()` passes `windowsHide: true`, alongside `detached: true`, not instead of it.** A fourth real
  run (2026-11-09), past the first three fixes, saw the Python server pop up its own separate console window —
  always empty, since its stdout/stderr already go to `logPath` (see "How it works" above), not to any console.
  Node's own docs name `windowsHide` as exactly the flag for suppressing that window (a no-op on every other
  OS); `detached` stays, since it still does the one thing Windows honours about it (`server.ts`'s own top
  comment). New regression test spies on `node:child_process`'s own `spawn` to check the actual options object
  passed, since `windowsHide`, unlike `detached`, leaves nothing on the resulting `ChildProcess` for a test to
  read back afterwards.
* **The shared menu manifest, one more consumer.** `manifest.py`
  (`clients/linux/src/claudia_shell_gtk/manifest.py`) stays the one source of truth for
  File/Edit/Format/View/Tools/Config/Help across every app and shell. `generate_menu.py` imports it (no GTK, by
  the same discipline `manifest.py` was already built to) and writes `src/generated/menu.<app>.json`; `menu.ts`
  turns that into Neutralino's `WindowMenuItem[]` with **no relocation and no `role` reading** — unlike macOS's
  `buildMainMenu()`, nothing is pulled into a leading application menu (D44: only macOS does that), and the Cocoa
  selectors D158 added to the manifest for macOS's `role` field are carried straight through `generate_menu.py`'s
  JSON output unused (`menu.ts`'s own top comment says why: Windows menu items have no native `action` slot to
  route a Cocoa selector through in the first place). `gtkAccelToWindowsShortcut()` translates `<Primary>letter`
  accelerators to the `Ctrl+Letter` shape Neutralino's `WindowMenuItem.shortcut` expects, display-only — the real
  keyboard handling still lives in the web app, same as every other shell.
* **Quit and About both go to the page.** `page-bridge.ts`'s `routeMenuClick()` sends `file.quit` straight to
  `Neutralino.app.exit()` (the one case the shell handles itself, because the process has to end either way,
  whether or not Quit sits in an application menu). `help.about` is `Kind.SHELL` in the manifest (GTK shows its
  own dialog for it), but Neutralino has no native About panel on any platform (D158 point 4), so — like on macOS
  — it is forwarded to the page like any other action; `AboutDialog.vue` already exists and needs no change.
* **The binary runs directly, with no bundle step.** macOS needs `app-bundle.ts` because the Dock, the
  application-menu heading and Activity Monitor all read a running process's bundle identity (`CFBundleName`),
  which a bare downloaded binary does not have. Windows has no equivalent identity source to fix: the taskbar and
  the window's own title bar both read `neutralino.config.json`'s `modes.window.title`, which this client already
  sets per app the same way it always did on Linux and macOS, so `launch.ts` spawns the downloaded binary as-is.
* **`<input type="file">` is expected to need no shell-side help, unlike macOS — not yet confirmed.** WKWebView
  (the engine behind Neutralino's macOS binary) shows no native Open panel for a file input unless the host
  implements a WKUIDelegate method for it, which Neutralino's generic binary does not — a real bug the owner hit
  on her own Mac, worked around there by `file-dialog.ts`. WebView2 (the engine behind Neutralino's Windows
  binary) is Chromium, and Chromium has handled `<input type="file">` with its own native picker since long
  before Neutralino existed, so the same workaround is not expected to be needed here. `inject-entry.ts`'s own top
  comment flags this as a hypothesis, not a confirmed result — if a real run on Windows finds the picker broken
  after all, a Windows `file-dialog.ts` can be added the same way macOS's was: the DOM/Neutralino surfaces
  (`Neutralino.os.showOpenDialog`, `Neutralino.filesystem.readBinaryFile`) are identical between the two shells.

## Tests

```
cd clients/windows
npm test               # vitest: identity, paths, server (incl. freePort, log capture), menu, page-bridge, launch, build-inject -- 63 tests
npm run typecheck       # tsc --strict over src/ and tests/
python3 -m pytest tools/tests   # generate_menu.py: 10 tests
npm run check-menu      # fails if src/generated/menu.*.json has drifted from manifest.py
```

Nothing here starts a real Neutralino binary or opens a real window — `installBridge()` in `page-bridge.ts` is the
one function with no test of its own, because what it calls only exists once `window.Neutralino` is real.
Everything pure around it (`routeMenuClick`, `applyActionStates`, `nextCheckedTarget`, and the whole of `menu.ts`)
is tested without one.

## Not verified (needs a real Windows machine)

1. **D159's core mechanic on Windows.** Confirmed on macOS; expected, not confirmed, to carry over unchanged (see
   this file's own opening note).
2. **`<input type="file">` needing no workaround.** This README's and `inject-entry.ts`'s own reasoning above —
   plausible from how WebView2 and Chromium behave, not checked by clicking the button on a real machine.
3. **The dual native-menu-plus-page-dispatch interaction** for composes' own editing commands on a real document,
   rather than a generic text field.
4. **Orphaned server processes when the shell is killed outright, rather than closed.** Flagged as a known open
   issue rather than solved here (see "Not done" below) — the user's own explicit choice for this first version,
   matching how macOS flags the same gap for its own missing PDEATHSIG equivalent.
5. **A clean machine.** This client was built and tested in a Linux sandbox; the four real Windows runs so far
   (2026-11-09, same Windows VM, Git Bash) each got one step further: past a fixed build-time bug, then a fixed
   `uv sync` dependency-group bug, then a fixed entry-point-guard bug that had `main()` never being called at
   all, then a fixed `windowsHide` gap that popped up a confusing, empty console window for the server (see "How
   it works" above and `claudiaoffice-log/notes/e5-11-windows-client.md`'s "First real run" through "Fourth real
   run"). The fourth run is also the first to reach `LocalServer.checkReady()`'s own 30-second startup timeout
   without a clear enough log to say why yet (see that run's own notes) — not yet resolved, and genuinely open:
   no older Windows version, no screen reader, no second machine either. One thing not yet worth acting on but
   worth checking once a run gets past the server answering: whether the Microsoft Edge WebView2 Runtime is
   present on the target machine. It ships with Windows 11 by default, but a trimmed VM image may lack it; if a
   future run gets as far as actually spawning the Neutralino binary (`buildShellCommand()`'s own command, with
   `stdio: 'inherit'`) and still shows no window, that is the first place to look, since it would be expected to
   produce some console output of its own at that point.

## Not done

Packaging (a real installer, `.ico`, codesigning, a Start Menu shortcut); computes and creates (only `composes`
has an `apps/<app>/` folder — `packaged: false` in `identity.ts` for the other two); printing as a contract message (D158 point 2 — `Neutralino.window.print()` exists and is in
`NeutralinoLike`, but nothing calls it yet); **no Windows Job Object or other mechanism to clean up an orphaned
server process if the shell is killed outright rather than closed** — `server.ts`'s own top comment documents the
underlying gap (Windows has no POSIX process groups or real signals; `kill()` is already the hard stop, with no
softer step before it), and this first version deliberately does not build a solution for the "the shell itself is
hard-killed" case, matching how macOS also leaves its own equivalent gap open rather than building a fix nobody
has asked for yet; `nativeAllowList`/`filesystemScopes` are trimmed to the four methods this client actually calls
today (`app.exit`, `window.setMainMenu`, `window.print`, `events.on`) but have not been re-checked against a later
Neutralino upgrade (D157 asks for that on every version bump); translations; single-instance behaviour; a CI job
for this package (same as macOS — see its own README's "Not done"; the Linux client has one job in the main gate,
this and macOS do not yet).
