# Claudia for macOS and Windows (claudia-shell-neutralino)

The native client of Claudia for macOS and Windows: a thin Neutralino window around the one web frontend (D42–D44) and a
small native core in Node, for all three apps, one package for both systems (D660). It is the same discipline the Linux
client (`clients/linux/`) follows for GTK, and it speaks the same shell contract (`clients/contract/`). Its command line
is the same on all three systems.

```
claudia-composes  [--server URL] [--debug]      one command per app, the same program (like Linux)
claudia-computes  [--server URL] [--debug]
claudia-creates   [--server URL] [--debug]
```

Without `--server` the window uses the local server of the three apps on this computer (D445), and starts it if none
runs. With it, no server is started: the
window connects to that one (`https://host[:port]`, a bare host means https, plain `http` only for this computer),
after the same checks as the Linux client (D242): it answers, it is a Claudia server, it runs **this window's app**,
and its HTTPS certificate is one this computer trusts (the Mac's keychain, Windows' certificate store). A window shows servers of its own app only; the list of servers
belongs to the shell (`shell.json`, D243) and the web app's connect dialog works through the contract's `connect` and
`servers` messages.

## How it is built (D251)

Neutralino cannot be injected into a page that it did not serve: the page gets no token and the client library is
never started (spikes 1–5, 2026-11-10; this is why the first design, D159, never had native menus — the menu in the
earlier demo was the web app's own). So the window is built the other way round:

```
 Neutralino window ── shows ──▶ shell page   apps/<app>/index.html, served by Neutralino itself (so it has the token)
                                 │  │            builds the native menu, shows status messages
                                 │  └─ <iframe> ─▶ the Claudia web app   local http://127.0.0.1:<port>, or any https server
                                 │                   │ postMessage: the shell contract (hello, welcome, action, connect, servers…)
                                 │ ◀─────────────────┘ the shell page accepts it only from its own frame and only from the origin it opened
                                 │ Neutralino.extensions.dispatch / app.broadcast
                                 ▼
                          native core (Node extension, apps/<app>/ext/core.mjs, started and ended by Neutralino)
                             checks of a server, the server list, settings, the local server's life
```

* **The shell page** (`shell-page.ts`, bundled to `shell/shell.js`) loads only `js/neutralino.js` (never
  `__neutralino_globals.js`, D157), sets the native menu, and answers the web app's contract messages (`bridge.ts`).
  Menu → `action` messages; `action_state` → menu items; `file.quit` and the window's close button end the
  application (`app.exit`; Neutralino's `exitProcessOnClose` is off on both platforms, D506, D660).
* **The web app** needs one small thing: when it is framed (`web/app/lib/shell-bridge.ts`, `detectParentSink`) it posts to
  its parent window and hears only the parent, and only when that is a page on this computer's loopback.
* **The native core** (`core.ts`, bundled to `ext/core.mjs`) is a Node process that Neutralino starts with the window
  (an *extension*). It runs `connection.ts` (the checks), `connector.ts`/`servers.ts`/`settings.ts` (the list),
  `desktop-server.ts`/`local-server.ts`/`server.ts` (the local server of the three apps, D445) and `files.ts` with the
  platform's dialogs (the page's files, D501). When the window ends, so does the core: it lets go of the shared server, which stops by
  itself once nothing is connected.
* **The launcher** (`launch.ts`, `cli.ts`) finds the Neutralino binary, on a Mac wraps it in a minimal `.app` (so macOS
  shows the app's name, see `platform/macos-app-bundle.ts`), puts the core's command into the app's
  `neutralino.config.json` for the run (the absolute `node` -- on Windows its 8.3 short name when the path has a space --,
  `--use-system-ca` where Node knows the flag (22.15+), so HTTPS trusts what the computer trusts, `--app`, `--server`;
  `core-command.ts`), runs the binary with `--path`, and puts the default back when the window ends. Nothing is left to be
  inherited.

```
src/
  cli.ts              the command line (parseArgs)                                  launch.ts       find, bundle, start
  identity.ts         the three apps: title, application id, server model           paths.ts        folders, frontend and python lookup
  contract.ts         the shell contract, checked like the schema (tests do both)   bridge.ts       the shell's side of the conversation
  servers.ts          addresses and the server list rules                           settings.ts     shell.json, atomic writes
  connection.ts       the checks before a server is shown                           connector.ts    connect, remember, newest request wins
  core.ts             the native core                                               core-entry.ts   the extension program (core-command.ts: its command)
  core-protocol.ts    page <-> core messages                                        extension.ts    the Neutralino extension link (WebSocket)
  local-server.ts     the local server, put together                                server.ts       start, wait for, stop one server process
  desktop-server.ts   the one server of the three apps (D445)                       files.ts        the page's files (D501, D502)
  file-protocol.ts    page <-> core file messages                                   menu.ts / menu-actions.ts   the native menu from the shared manifest
  shell-page.ts       the shell page's logic                                        shell-page-entry.ts  its wiring to the browser
  platform/           what is macOS' or Windows' own (D660), and nothing else:
    id.ts               which platform a build is for              host.ts / page.ts   the native side's and the page's differences
    macos.ts            ~/Library, the .app, signals               windows.ts          %LOCALAPPDATA%, taskkill, 8.3 names
    macos-dialogs.ts    the Mac's panels, through osascript        windows-dialogs.ts  the common dialogs, through PowerShell
    macos-menu.ts       the application menu, Cocoa roles          windows-menu.ts     the window menu, Ctrl+… shortcuts
    macos-app-bundle.ts the minimal .app                           setup-problem.ts    what is missing, for the person
  generated/          menu.<app>.json, from clients/linux's manifest.py
tools/  generate_menu.py (menus), build-shell.mjs (per app and platform: index.html, shell/shell.js, ext/core.mjs), shell-page.template.html
bin/    claudia-composes, claudia-computes, claudia-creates (one shim each; on Windows npm makes `.cmd` files of them)
apps/<app>/   neutralino.config.json, icons; built (not checked in): index.html, shell/, ext/; fetched by `neu update`: bin/, js/
```

## One package for two platforms (D660)

macOS and Windows run the same code: everything in `src/` but `src/platform/`, which holds what is the operating
system's own -- where the suite keeps its files, where `uv sync` puts the server's Python, Neutralino's binary and (on a
Mac) the `.app` around it, the dialogs, how a server's process tree is ended, the menu and the words a person reads. The
launcher and the tests ask the operating system they run on; the bundles are built for one platform
(`npm run build:macos`, `npm run build:windows`; `npm run build` builds for the computer it runs on), and a Windows build
behaves like Windows wherever it runs, as CI's end-to-end test does on Linux. Both platforms' code is tested on every
runner. The checked-in `neutralino.config.json` of each app holds the core's command for both (`commandDarwin`,
`commandWindows`), and on both the window is closed through the page (D506), so it is one file.

Before D660 these were two packages, `clients/macos` and `clients/windows`, of which half the files were identical copies
(CODE-14).

## Packaged mode (D741)

A client installed by the Windows installer has a `packaged.json` next to its `package.json` (`{"web": ..., "server": ...}`,
paths relative to the client's folder). With it the launcher gives the core `CLAUDIA_WEB_DIR` and `CLAUDIA_SERVER_EXE`
(unless you set your own), and runs the window from a copy of the app's folder in `<Claudia folder>\run\<app>`, because the
installation may be read-only. `CLAUDIA_SERVER_EXE` can also be set by hand to start a self-contained `claudia-server`
instead of `CLAUDIA_SERVER_PYTHON -m claudia_server`; it wins when both are set.

## Running it from a checkout

### On a Mac

From the repository root: `./start-mac-client.sh [composes|computes|creates] [--server URL] [--debug]` does
everything below (it rebuilds the web app and this client on every start; `CLAUDIA_SKIP_WEB_BUILD=1` /
`CLAUDIA_SKIP_NEUTRALINO_BUILD=1` skip that). By hand:

```
uv sync --no-dev                           # the server's Python 3.14 environment: .venv
(cd web && npm ci && npm run build)        # the web frontend: web/.output/public
cd clients/neutralino && npm ci && npm run build   # tsc, then per app: the shell page, its script and the core
(cd apps/creates && npx @neutralinojs/neu update)   # the pinned Neutralino binary and client library (D157), per app
node dist/launch.js creates [--server https://demo.claudia-office.de]
```

Needs Node 22 or newer. **The checkout must be in a folder without spaces in its path** (Neutralino starts the core with
a command line that contains the folder; the launcher refuses a path with a space and says so).

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv/bin/python` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web/.output/public`. If set, it is the only candidate: a wrong path is reported. |
| `CLAUDIA_SERVER_PORT` | The port of the local server. Default: 8765, the port of `./start.sh` (D504); a Claudia server already there is used. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `apps/<app>/bin/neutralino-mac_<arch>`, where `neu update` puts it. |

The three apps share one local server (D445, as on Windows): documents are in
`~/Library/Application Support/Claudia/documents/<app>`, the server's state, `server.log` and `desktop-server.json` (its
port: 8765, D504) in `…/Claudia/state`; each app's `…/Claudia/<app>/state/shell.log` is its core's log;
`~/Library/Application Support/Claudia/shell.json` holds the server lists. The server stops by itself ten minutes after
its last window has closed.
`--debug` prints where these are.


### On Windows

From the repository root: `start-win-client.cmd [composes|computes|creates] [--server URL] [--debug]` does everything
below (it rebuilds the web app and this client on every start; `CLAUDIA_SKIP_WEB_BUILD=1` / `CLAUDIA_SKIP_NEUTRALINO_BUILD=1`
skip that). By hand:

```
uv sync --no-dev                           # the server's Python 3.14 environment: .venv. --no-dev skips the repo's own
                                           # docs/lint/test tooling, which needs a C compiler on a very new Python
                                           # (the PyYAML source build found by the second real run, 2026-11-09)
(cd web && npm ci && npm run build)        # the web frontend: web\.output\public
cd clients\neutralino && npm ci && npm run build   # tsc, then per app: the shell page, its script and the core
(cd apps\creates && npx @neutralinojs/neu update)   # the pinned Neutralino binary and client library (D157), per app
node dist\launch.js creates [--server https://demo.claudia-office.de]
```

To have `claudia-composes`, `claudia-computes` and `claudia-creates` as commands, run `npm link` in `clients\neutralino`: npm
makes `claudia-<app>.cmd` shims from `package.json`'s `bin`, and they take the same arguments as the shell scripts do on
the other two systems.

Needs Node 22 or newer. **The checkout must be in a folder without spaces in its path** (Neutralino starts the core with a
command line that contains the folder; the launcher refuses a path with a space and says so).

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv\Scripts\python.exe` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web\.output\public`. If set, it is the only candidate: a wrong path is reported. |
| `CLAUDIA_SERVER_PORT` | The port of the local server. Default: 8765, the port of `./start.sh` (D504); a Claudia server already there is used. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `apps\<app>\bin\neutralino-win_x64.exe`, where `neu update` puts it. |

If the window stays on "Starting…" the core could not be reached: the page says so after 20 seconds and names the logs
(`shell.log` of the core in `%LOCALAPPDATA%\Claudia\<app>\state`, `server.log` of the server in
`%LOCALAPPDATA%\Claudia\state`); start the app again with `--debug` to open the window's web inspector for the shell
page's console. A `python.exe` left over from an older build may hold the documents folder: end it in the Task Manager.

## Tests

```
cd clients/neutralino
npm test               # vitest: the contract against the JSON schema, the checks against real http/https servers, the core
                       # built for each platform as a real process against a fake Neutralino, the shell page, the launcher, …
npm run typecheck      # tsc --strict over src/ and tests/
uv run --no-project --with pytest python -m pytest tools/tests   # generate_menu.py
npm run check-menu     # fails if src/generated/menu.*.json has drifted from manifest.py
npm run build:macos && (cd ../../web && npm run e2e:macos-shell)       # the window in Chromium, as a Mac build
npm run build:windows && (cd ../../web && npm run e2e:windows-shell)   # the same, as a Windows build
```

The two e2e scripts in `web/e2e/` (CI runs them in the `e2e` job; the unit tests also run on Windows itself in the
`neutralino-windows` job) run, for each of the three apps, the built shell page, the built core as a real process, a real
server and the real web app in the frame, with only Neutralino's client library faked: the handshake, the web app's menu
bar gives way to the native one, a native "Save New Checkpoint…" click opens the web app's dialog, and the window's end
stops the server it started. And once more with `--server`. Each needs the build of its own platform, so build right
before it.

## Not verified

### On a Mac

Everything above is tested on Linux with stand-ins: a fake Neutralino for the core's protocol, fakes for the shell page,
real local servers for the checks. What a Linux run cannot show, and what the first run on a Mac must:

1. **The whole window**, built from these files: the shell page gets its token, the native menu appears next to the
   Apple logo, the frame shows the web app (local http, and a remote https server), and the web app's menu bar is
   replaced by the native one. Spike 5 proved each part separately (page with token, menu, frame of an https page,
   extension round trip); this is the first time they run together.
2. ~~The conversation between the frame and the shell page~~ -- shown in Chromium by `web/e2e/macos-shell.cjs`
   (`npm run build:macos`, then `cd web && npm run e2e:macos-shell`; CI runs it) with the real shell page, the real core as a process, a real server
   and the real web app, only Neutralino's client library faked: for each of the three apps the web app's menu bar
   collapses and a native "Save New Checkpoint…" click opens the web app's dialog, and the window's end stops the server it
   started; with `--server` the given server is shown and left running. What remains is WKWebView itself, and a
   **remote server whose web app predates the framed-page support** (web commit 55a9742): there the page never says
   hello, keeps its own menu bar, and the native menu cannot drive it; the window's console says so after five seconds.
3. **HTTPS with a certificate from a certificate authority that macOS trusts**, through the Node core's own check
   (`--use-system-ca`), against a real server; and that a server certificate nobody vouches for is refused with
   "not issued by an authority this computer trusts".
4. **Cmd+C/V/X/Z in the web app** inside the frame (the Edit menu's Cocoa actions work on the focused field; spike 5:
   the shortcuts themselves did not fire, the menu items did).
5. **The shared server** (D445): the window lets go of it, and it stops by itself ten minutes later; a window killed
   with `kill -9` was not tried.
6. **The panels** (D501, D502): that NSOpenPanel and NSSavePanel, run by `osascript` in JavaScript for Automation, come
   up in front of the window, and that `open` shows a PDF in Preview. The e2e script only shows that the request goes
   from the page through the shell page to the core and back.


### On Windows

Everything above is tested on Linux with stand-ins, and the unit tests also run on Windows in CI. What a Linux run cannot
show, and what the first run on Windows must. **This client has not been run on Windows in its new form**, nor since
D660 made it one package with the macOS client and closes its window through the page as on a Mac (`exitProcessOnClose`
off, the page ends the app on `windowClose`): the first run should close each window with its close button; the earlier
form ran four times on the owner's Windows VM and each run found a bug (`claudiaoffice-log/notes/e5-11-windows-client.md`),
the last of them, a server that did not answer within 30 seconds, never explained (a virus scanner on a fresh `.venv` is the
suspicion; `server.log` will say).

0. **The shared server** (D445): three windows started within a second of each other end up on one server and one port;
   a window opened later finds it; the server leaves ten minutes after the last window; a window whose server was ended
   in the Task Manager starts it again. Tested on Linux with a stand-in server and the real folder lock, not on Windows
   (`msvcrt.locking`, detached start, `taskkill`).
1. **The whole window**, built from these files: the shell page gets its token (the same mechanism that spike 5 proved on a
   Mac), the native menu appears, the frame shows the web app (local http, and a remote https server).
2. **The core's command with Windows paths.** `${NL_PATH}` and the absolute path of node in a command that Neutralino splits at
   spaces (see above); the extension key is `commandWindows`. If the window stays on "Starting…", the log of the core is
   where to look; whether a console window flashes up for the core is not known either.
3. **HTTPS with a certificate from an authority that Windows trusts**, through the Node core's own check
   (`--use-system-ca`, Node 22.15+), against a real server; and that a certificate nobody vouches for is refused with "not
   issued by an authority this computer trusts".
4. **Edit shortcuts in the frame** (Ctrl+C/V/X/Z in the web app: WebView2 handles them itself; the menu items go through the
   page), and **the dialogs** (D501): that the Windows Forms Open and Save dialogs that the core shows through PowerShell
   come up in front of the window (owned by a top-most form) and how long PowerShell takes to show them; and that a PDF
   to print opens in the application Windows has for PDFs (D502).
5. **Orphans**: the core ends with the window and stops the server, and now the whole tree of it; a window or core killed
   with `taskkill /f` was not tried (D161 stays open for it), nor was `taskkill /T` against the real `uv` interpreter.
6. **WebView2 Runtime** on a trimmed machine image (Windows 11 has it), an older Windows, a screen reader.
7. `start-win-client.cmd` with arguments (`--server`, an app name): written carefully, and not run.

## Known gaps and follow-ups

* **Self-signed certificates** (D245, trust by pin) are not built, for any desktop client yet: such a server is refused.
* **Links that open a new window** from the framed page are not handled by the shell yet. Files and printing go
  through the contract (`pick_file`, `save_file`, D501, D502).
* **The frame has no `sandbox`** attribute: untested on a Mac, so not guessed at. The framed page is cross-origin and
  cannot reach Neutralino; a sandbox would add a second line of defence.
* **The shell page's status screens** (starting, connecting, cannot start) are plain text; no design has been agreed.
* Messages of the shell are English only (the Linux client has no catalogs either).
* macOS: no `.app` bundle you install, no `.icns`, signing or notarization; no macOS CI (the pipeline's macOS image fails
  at the moment). The Redo menu item has no shortcut (no confirmed Neutralino grammar for Cmd+Shift+Z).
* Windows: the installer (`packaging/windows/`, D742) has the `.ico` and the Start menu shortcuts and is not signed (D744); no file associations; shortcuts in the menu are display-only.
* `neutralino.config.json` is rewritten for a run and restored after, so a launcher killed outright (a closed console is
  handled, `kill -9` or `taskkill /f` is not) leaves the core's command in it until the next start (`git diff` shows it).
