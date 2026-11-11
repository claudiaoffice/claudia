# Claudia for Windows (claudia-shell-windows)

The native client of Claudia for Windows: a thin Neutralino window around the one web frontend (D42–D44) and a small
native core in Node, for all three apps. It is the same discipline the Linux client (`clients/linux/`) follows for GTK
and the macOS client (`clients/macos/`) for Cocoa, and it speaks the same shell contract (`clients/contract/`). Its
command line is the same on all three systems; only the shim that starts it is Windows' own (`claudia-<app>.cmd`).

```
claudia-composes  [--server URL] [--debug]      one command per app, the same program (like Linux and macOS)
claudia-computes  [--server URL] [--debug]
claudia-creates   [--server URL] [--debug]
```

Without `--server` the window starts the app's own server on this computer. With it, no server is started: the
window connects to that one (`https://host[:port]`, a bare host means https, plain `http` only for this computer),
after the same checks as the Linux client (D242): it answers, it is a Claudia server, it runs **this window's app**,
and its HTTPS certificate is one this computer trusts (Windows' own certificate store, see below). A window shows
servers of its own app only; the list of servers belongs to the shell (`shell.json`, D243) and the web app's connect
dialog works through the contract's `connect` and `servers` messages.

## How it is built (D251)

Neutralino cannot be injected into a page that it did not serve: the page gets no token and the client library is
never started (spikes 1–5 on a Mac, 2026-11-10; `claudiaoffice-log/notes/e5-11-macos-client-complete.md`). This client
was first built the other way (D159: the window loads the server's address and Neutralino's API is injected into it),
so it very likely had the same gap, and it has been rebuilt on the design that D251 records for macOS:

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
  Menu → `action` messages; `action_state` → menu items; `file.quit` ends the application.
* **The web app** needs one small thing, which the macOS client's patch carries too: when it is framed
  (`web/app/lib/shell-bridge.ts`, `detectParentSink`) it posts to its parent window and hears only the parent, and only
  when that is a page on this computer's loopback.
* **The native core** (`core.ts`, bundled to `ext/core.mjs`) is a Node process that Neutralino starts with the window
  (an *extension*, `commandWindows` in the config). It runs `connection.ts` (the checks), `connector.ts`/`servers.ts`/
  `settings.ts` (the list), and `local-server.ts`/`server.ts` (the app's own server). When the window ends, so does the
  core, and it stops the server: this is also what stops a server when the window is killed (`D161`, below).
* **The launcher** (`launch.ts`, `cli.ts`) finds the Neutralino binary, puts the core's command into the app's
  `neutralino.config.json` for the run (the absolute `node`, `--use-system-ca` where Node knows the flag (22.15+), so HTTPS
  trusts what the Windows certificate store trusts, `--app`, `--server`; `core-command.ts`), runs the binary with `--path`,
  and puts the default back when the window ends.

What is Windows' own, against macOS:

* **The menu is one ordinary window menu** (`menu.ts`): File, Edit, Format, View, Tools, Config, Help in the manifest's own
  order. No application menu to move About and Quit into (D44), no Cocoa `role` for the Edit items (D158 point 1): every
  Edit item is a plain contract `action` for the page, as on Linux. Quit is the shell's own (`Neutralino.app.exit()`);
  About is the page's (`nativeAbout: false`). Shortcuts in the menu are display-only (`Ctrl+N`...).
* **No `.app` bundle** (`app-bundle.ts` has no counterpart): the taskbar and the title bar read the window's title from the
  config. The binary is `neutralino-win_x64.exe`, the only Windows binary Neutralino 6.8.0 publishes.
* **The path of node usually has a space** (`C:\Program Files\nodejs\node.exe`) and Neutralino cannot pass a space to the
  core. `launch.ts` uses the 8.3 short name (`C:\PROGRA~1\...`) when there is one, and otherwise starts the core as a
  plain `node` from `PATH`, which the launcher has set to put the running node's folder first (it says so on the console).
* **`Path` is not `PATH`** to `process.env` on Windows, which keeps the spelling it was given: `launch.ts` sets variables
  through `environmentWith`, so the child never gets two (a test pins this).
* **The server is stopped with its whole process tree** (`server.ts`, `taskkill /pid N /T /F`): the interpreter that
  `uv sync` puts in `.venv\Scripts\python.exe` is a launcher that starts the real one as its child, and
  `ChildProcess.kill()` would end only the launcher. Windows has no gentler signal, so there is no grace period.
* **Folders:** `%LOCALAPPDATA%\Claudia\<app>\documents` and `...\state` (with `server.log` and `shell.log`);
  `%LOCALAPPDATA%\Claudia\shell.json` holds the server lists. `--debug` prints where these are.

```
src/
  cli.ts              the command line (parseArgs)                                  launch.ts       find, configure, start
  identity.ts         the three apps: title, application id, server model           paths.ts        folders, frontend and python lookup
  contract.ts         the shell contract, checked like the schema (tests do both)   bridge.ts       the shell's side of the conversation
  servers.ts          addresses and the server list rules                           settings.ts     shell.json, atomic writes
  connection.ts       the checks before a server is shown                           connector.ts    connect, remember, newest request wins
  core.ts             the native core                                               core-entry.ts   the extension program (core-command.ts: its command)
  core-protocol.ts    page <-> core messages                                        extension.ts    the Neutralino extension link (WebSocket)
  local-server.ts     the app's own server                                          server.ts       start, wait for, stop it (the tree, on Windows)
  shell-page.ts       the shell page's logic                                        shell-page-entry.ts  its wiring to the browser
  menu.ts / menu-actions.ts   the native menu from the shared manifest
  generated/          menu.<app>.json, from clients/linux's manifest.py
tools/  generate_menu.py (menus), build-shell.mjs (per app: index.html, shell/shell.js, ext/core.mjs), shell-page.template.html
bin/    claudia-composes, claudia-computes, claudia-creates (one shim each; npm makes the .cmd files from them)
apps/<app>/   neutralino.config.json, icons; built (not checked in): index.html, shell/, ext/; fetched by `neu update`: bin/, js/
```

## Running it from a checkout

From the repository root: `start-win-client.cmd [composes|computes|creates] [--server URL] [--debug]` does everything
below (it rebuilds the web app and this client on every start; `CLAUDIA_SKIP_WEB_BUILD=1` / `CLAUDIA_SKIP_WINDOWS_BUILD=1`
skip that). By hand:

```
uv sync --no-dev                           # the server's Python 3.14 environment: .venv. --no-dev skips the repo's own
                                           # docs/lint/test tooling, which needs a C compiler on a very new Python
                                           # (the PyYAML source build found by the second real run, 2026-11-09)
(cd web && npm ci && npm run build)        # the web frontend: web\.output\public
cd clients\windows && npm ci && npm run build   # tsc, then per app: the shell page, its script and the core
(cd apps\creates && npx @neutralinojs/neu update)   # the pinned Neutralino binary and client library (D157), per app
node dist\launch.js creates [--server https://demo.claudia-office.de]
```

To have `claudia-composes`, `claudia-computes` and `claudia-creates` as commands, run `npm link` in `clients\windows`: npm
makes `claudia-<app>.cmd` shims from `package.json`'s `bin`, and they take the same arguments as the shell scripts do on
the other two systems.

Needs Node 22 or newer. **The checkout must be in a folder without spaces in its path** (Neutralino starts the core with a
command line that contains the folder; the launcher refuses a path with a space and says so).

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv\Scripts\python.exe` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web\.output\public`. If set, it is the only candidate: a wrong path is reported. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `apps\<app>\bin\neutralino-win_x64.exe`, where `neu update` puts it. |

If the window stays on "Starting…" the core could not be reached: the page says so after 20 seconds and names the logs
(`shell.log` of the core, `server.log` of the server, both in `%LOCALAPPDATA%\Claudia\<app>\state`); right-click in the
window and choose Inspect for the shell page's console.

## Tests

```
cd clients\windows
npm test               # vitest: the contract against the JSON schema, the checks against real http/https servers, the core
                       # and the built `ext\core.mjs` as a real process against a fake Neutralino, the shell page, the launcher, …
npm run typecheck      # tsc --strict over src/ and tests/
python -m pytest tools/tests    # generate_menu.py
npm run check-menu     # fails if src/generated/menu.*.json has drifted from manifest.py
cd ..\..\web && npm run e2e:windows-shell   # the window in Chromium: see below
```

`web/e2e/windows-shell.cjs` (`npm run e2e:windows-shell` in `web/`; CI runs it in the `e2e` job, the unit tests also in the
`windows-client` job on Windows itself) runs, for each of the three apps, the built shell page, the built core as a real
process, a real server and the real web app in the frame, with only Neutralino's client library faked: the handshake, the web
app's menu bar gives way to the native one, a native "Save New Checkpoint…" click opens the web app's dialog, and the window's
end stops the server it started. And once more with `--server`.

## Not verified (needs a real Windows machine)

Everything above is tested on Linux with stand-ins, and the unit tests also run on Windows in CI. What a Linux run cannot
show, and what the first run on Windows must. **This client has not been run on Windows in its new form**; the earlier
form ran four times on the owner's Windows VM and each run found a bug (`claudiaoffice-log/notes/e5-11-windows-client.md`),
the last of them, a server that did not answer within 30 seconds, never explained (a virus scanner on a fresh `.venv` is the
suspicion; `server.log` will say).

1. **The whole window**, built from these files: the shell page gets its token (the same mechanism that spike 5 proved on a
   Mac), the native menu appears, the frame shows the web app (local http, and a remote https server).
2. **The core's command with Windows paths.** `${NL_PATH}` and the absolute path of node in a command that Neutralino splits at
   spaces (see above); the extension key is `commandWindows`. If the window stays on "Starting…", the log of the core is
   where to look; whether a console window flashes up for the core is not known either.
3. **HTTPS with a certificate from an authority that Windows trusts**, through the Node core's own check
   (`--use-system-ca`, Node 22.15+), against a real server; and that a certificate nobody vouches for is refused with "not
   issued by an authority this computer trusts".
4. **Edit shortcuts in the frame** (Ctrl+C/V/X/Z in the web app: WebView2 handles them itself; the menu items go through the
   page), and `<input type="file">`, which WebView2 should open a picker for without help (macOS needs a contract message,
   `pick_file`) — a hypothesis from the engines' documentation.
5. **Orphans**: the core ends with the window and stops the server, and now the whole tree of it; a window or core killed
   with `taskkill /f` was not tried (D161 stays open for it), nor was `taskkill /T` against the real `uv` interpreter.
6. **WebView2 Runtime** on a trimmed machine image (Windows 11 has it), an older Windows, a screen reader.
7. `start-win-client.cmd` with arguments (`--server`, an app name): written carefully, and not run.

## Known gaps and follow-ups

* **Self-signed certificates** (D245, trust by pin) are not built, for any desktop client yet: such a server is refused.
* **Printing and links that open a window** from the framed page are not handled by the shell yet (D158 point 2); nor is
  **`pick_file`**, if WebView2 turns out to need it.
* **The frame has no `sandbox`** attribute: untried, so not guessed at. The framed page is cross-origin and cannot reach
  Neutralino; a sandbox would add a second line of defence.
* **The shell page's status screens** (starting, connecting, cannot start) are plain text; no design has been agreed.
* Messages of the shell are English only (the Linux client has no catalogs either).
* No installer, `.ico`, signing or Start Menu shortcut; `neutralino.config.json` is rewritten for a run and restored after,
  so a launcher killed outright (a closed console is handled, `taskkill /f` is not) leaves the core's command in it until the
  next start (`git diff` shows it).
* Redo has no menu shortcut on macOS; here shortcuts are display-only for every item.
