# Claudia for macOS (claudia-shell-macos)

The native client of Claudia for macOS: a thin Neutralino window around the one web frontend (D42–D44) and a small
native core in Node, for all three apps. It is the same discipline the Linux client (`clients/linux/`) follows for GTK,
and it speaks the same shell contract (`clients/contract/`).

```
claudia-composes  [--server URL] [--debug]      one command per app, the same program (like Linux)
claudia-computes  [--server URL] [--debug]
claudia-creates   [--server URL] [--debug]
```

Without `--server` the window starts the app's own server on this computer. With it, no server is started: the
window connects to that one (`https://host[:port]`, a bare host means https, plain `http` only for this computer),
after the same checks as the Linux client (D242): it answers, it is a Claudia server, it runs **this window's app**,
and its HTTPS certificate is one this Mac trusts. A window shows servers of its own app only; the list of servers
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
  Menu → `action` messages; `action_state` → menu items; `file.quit` ends the application.
* **The web app** needs one small thing: when it is framed (`web/app/lib/shell-bridge.ts`, `detectParentSink`) it posts to
  its parent window and hears only the parent, and only when that is a page on this computer's loopback.
* **The native core** (`core.ts`, bundled to `ext/core.mjs`) is a Node process that Neutralino starts with the window
  (an *extension*). It runs `connection.ts` (the checks), `connector.ts`/`servers.ts`/`settings.ts` (the list), and
  `local-server.ts`/`server.ts` (the app's own server). When the window ends, so does the core, and it stops the
  server: this is also what keeps a killed window from leaving a server behind (macOS has no `PR_SET_PDEATHSIG`).
* **The launcher** (`launch.ts`, `cli.ts`) finds the Neutralino binary, wraps it in a minimal `.app` (so macOS shows
  the app's name, see `app-bundle.ts`), puts the core's command into the app's `neutralino.config.json` for the run (the absolute `node`, `--use-system-ca`
  where Node knows the flag (22.15+), so HTTPS trusts what the Mac trusts, `--app`, `--server`; `core-command.ts`), runs
  the binary with `--path`, and puts the default back when the window ends. Nothing is left to be inherited.

```
src/
  cli.ts              the command line (parseArgs)                                  launch.ts       find, bundle, start
  identity.ts         the three apps: title, bundle id, server model                paths.ts        folders, frontend and python lookup
  contract.ts         the shell contract, checked like the schema (tests do both)   bridge.ts       the shell's side of the conversation
  servers.ts          addresses and the server list rules                           settings.ts     shell.json, atomic writes
  connection.ts       the checks before a server is shown                           connector.ts    connect, remember, newest request wins
  core.ts             the native core                                               core-entry.ts   the extension program (core-command.ts: its command)
  core-protocol.ts    page <-> core messages                                        extension.ts    the Neutralino extension link (WebSocket)
  local-server.ts     the app's own server                                          server.ts       start, wait for, stop it
  shell-page.ts       the shell page's logic                                        shell-page-entry.ts  its wiring to the browser
  menu.ts / menu-actions.ts   the native menu from the shared manifest             app-bundle.ts   the minimal .app
  generated/          menu.<app>.json, from clients/linux's manifest.py
tools/  generate_menu.py (menus), build-shell.mjs (per app: index.html, shell/shell.js, ext/core.mjs), shell-page.template.html
bin/    claudia-composes, claudia-computes, claudia-creates (one shim each)
apps/<app>/   neutralino.config.json, icons; built (not checked in): index.html, shell/, ext/; fetched by `neu update`: bin/, js/
```

## Running it from a checkout

From the repository root: `./start-mac-client.sh [composes|computes|creates] [--server URL] [--debug]` does
everything below (it rebuilds the web app and this client on every start; `CLAUDIA_SKIP_WEB_BUILD=1` /
`CLAUDIA_SKIP_MACOS_BUILD=1` skip that). By hand:

```
uv sync --no-dev                           # the server's Python 3.14 environment: .venv
(cd web && npm ci && npm run build)        # the web frontend: web/.output/public
cd clients/macos && npm ci && npm run build   # tsc, then per app: the shell page, its script and the core
(cd apps/creates && npx @neutralinojs/neu update)   # the pinned Neutralino binary and client library (D157), per app
node dist/launch.js creates [--server https://demo.claudia-office.de]
```

Needs Node 22 or newer. **The checkout must be in a folder without spaces in its path** (Neutralino starts the core with
a command line that contains the folder; the launcher refuses a path with a space and says so).

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv/bin/python` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web/.output/public`. If set, it is the only candidate: a wrong path is reported. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `apps/<app>/bin/neutralino-mac_<arch>`, where `neu update` puts it. |

Documents are in `~/Library/Application Support/Claudia/<app>/documents`; its `state/` folder has `server.log` (the
server) and `shell.log` (the core); `~/Library/Application Support/Claudia/shell.json` holds the server lists.
`--debug` prints where these are.

## Tests

```
cd clients/macos
npm test               # vitest, 333 tests: the contract against the JSON schema, the checks against real http/https
                       # servers, the core and the built `ext/core.mjs` as a real process against a fake Neutralino, …
npm run typecheck      # tsc --strict over src/ and tests/
python3 -m pytest tools/tests   # generate_menu.py
npm run check-menu     # fails if src/generated/menu.*.json has drifted from manifest.py
```

## Not verified (needs a real Mac)

Everything above is tested on Linux with stand-ins: a fake Neutralino for the core's protocol, fakes for the shell page,
real local servers for the checks. What a Linux run cannot show, and what the first run on a Mac must:

1. **The whole window**, built from these files: the shell page gets its token, the native menu appears next to the
   Apple logo, the frame shows the web app (local http, and a remote https server), and the web app's menu bar is
   replaced by the native one. Spike 5 proved each part separately (page with token, menu, frame of an https page,
   extension round trip); this is the first time they run together.
2. ~~The conversation between the frame and the shell page~~ -- shown in Chromium by `web/e2e/macos-shell.cjs`
   (`cd web && npm run e2e:macos-shell`; CI runs it) with the real shell page, the real core as a process, a real server
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
5. **Orphans**: the core ends with the window and stops the server, but a window killed with `kill -9` was not tried.

## Known gaps and follow-ups

* **Self-signed certificates** (D245, trust by pin) are not built, for any desktop client yet: such a server is refused.
* **`<input type="file">` does not open a file panel** in the macOS web view (as in the earlier demo). The old
  workaround ran inside the page and cannot run in a cross-origin frame; it needs a contract message (`pick_file`).
* **Links that open a new window, and `window.print()`** from the framed page are not handled by the shell yet.
* **The frame has no `sandbox`** attribute: untested on a Mac, so not guessed at. The framed page is cross-origin and
  cannot reach Neutralino; a sandbox would add a second line of defence.
* **The shell page's status screens** (starting, connecting, cannot start) are plain text; no design has been agreed.
* Messages of the shell are English only (the Linux client has no catalogs either).
* No `.app` bundle you install, no `.icns`, signing or notarization; no macOS CI (the pipeline's macOS image fails
  at the moment). The Windows client, also Neutralino, very likely has the same injection problem and needs the same
  design (D251 notes).
* The Redo menu item has no shortcut (no confirmed Neutralino grammar for Cmd+Shift+Z).
