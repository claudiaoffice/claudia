# macOS client (E5.11), complete: three apps, command line, server flow, and why Neutralino is built the other way round

Written 2026-11-10 on the branch `macos-client-complete` (target branch given by the owner; handed over as patches, no
push access from this session). Scope as agreed: (1) bring the demo (`macos-client`, creates only) in and fix its
drift against main; (2) all three apps and the command line; (3) the native core with the server flow of the Linux
client (D241–D248), including HTTPS with certificates from an authority the Mac trusts. Stop after 3; CI, `.app`/`.dmg`,
signing and self-signed certificates (D245) later. Decision: **D251**. Code: `clients/macos/`; one small change in
`web/app/lib/shell-bridge.ts`; docs in `clients/macos/README.md`, `clients/contract/README.md`.

## What the spikes found (all on the owner's Mac, Neutralino 6.8.0, WKWebView)

The aim was to check D159 before building the server flow on it, as the first real run of the Linux-equivalent
flow was supposed to be a test, not the discovery.

1. **Spikes 1–4: the injection never gives the page a client.** With `injectGlobals`/`injectClientLibrary` on a page that
   Neutralino did not serve (http loopback or https), `window.Neutralino` exists, but the one-time token is empty and
   `Neutralino.init()` is never called, so every call hangs. `tokenSecurity: none` gives `NE_CL_IVCTOKN` instead, also
   inside an `.app` bundle. (An HTTPS-is-the-cause conclusion drawn on the way was wrong and was withdrawn.) The owner
   remembered the same error from the first development of the client, and could not remember how it had been avoided.
2. **The demo's own console agreed**: its title never changed, "the promise just hangs", and — the owner's correction —
   there had never been a native menu in the demo (the menu bar next to the Apple logo); the menu was always the web
   app's. The README's "native menu renders" (2026-11-07) was a misreading and is corrected in the README and CHANGELOG.
3. **Spike 5 proved the design that D251 records**: a page that Neutralino serves itself (`url: "/"`, a script tag for
   `js/neutralino.js` only) gets its token and calls `init()`; `window.setMainMenu` shows a real menu next to the Apple
   logo and its click event arrives; `https://example.com` and `https://demo.claudia-office.de` load in a full-window
   frame; the web app's welcome page can be typed into and a document created in the frame; a Node extension started by
   Neutralino (`enableExtensions`, `extensions: [{id, commandDarwin}]`) gets `{nlPort, nlToken, nlConnectToken,
   nlExtensionId}` on stdin, connects to `ws://localhost:<port>?extensionId=…&connectToken=…`, and page and extension
   talk with `Neutralino.extensions.dispatch(id, event, data)` and a WebSocket message `{id, method: 'app.broadcast',
   accessToken: nlToken, data: {event, data}}`. A cross-origin frame cannot read the shell page's `Neutralino` (a
   `SecurityError`). Keyboard shortcuts for Cmd+C/V did not fire; the Edit menu's Paste item worked in the framed
   remote page. 23 checks of the spike's test harness (jsdom) passed before it was sent.
4. WKWebView blocks mixed content: `fetch`, and probably `ws://127.0.0.1`, from an https page; a frame with an https page
   under an http shell page is fine, which is what makes the design possible for remote servers.

## What was built

* **Shell page and frame** (`shell-page.ts`, entry, `tools/shell-page.template.html`, `tools/build-shell.mjs`): the
  page, per app, with the generated menu baked in; status overlay for starting, connecting and failing.
* **Native core** (`core.ts`, `core-entry.ts`, `extension.ts`, `core-protocol.ts`): a port of Linux's `app.py` and the
  `Connector` wiring; `start`, `connect`, `servers`, `want_servers` in, `show`, `status`, `servers`, `connect_failed` out.
  It ends with the window and stops the local server (compensates for no `PR_SET_PDEATHSIG` on macOS).
* **The server flow of Linux, ported 1:1**: `contract.ts` (all eight message types, judged against the JSON schema by the
  tests, 52 cases), `servers.ts` (https by default, plain http only for loopback, no user info, path, query,
  fragment; an `xn--` name for internationalised hosts), `settings.ts` (`shell.json`, the same file format as Linux,
  other keys preserved, atomic writes), `connection.ts` (`/api/health` and `/api/docs`, a window connects only to its
  own app, TLS errors mapped to `certificate_expired`/`certificate_invalid`), `connector.ts` (newest request wins),
  `bridge.ts`. A certificate nobody trusts is refused ("not issued by an authority this computer trusts"), like Linux
  without a trust dialog. Node's CA list is the system's with `NODE_OPTIONS=--use-system-ca` (Node 22.15+), which the
  launcher sets only where Node knows the flag.
* **Three apps and the command line** (`cli.ts`, `launch.ts`, `bin/`, `start-mac-client.sh`):
  `claudia-<app> [--server URL] [--debug]`, `node dist/launch.js <app> …`. No app picker (a window is one app, D242).
* **Web app**: `detectParentSink` in `shell-bridge.ts` (the only change outside `clients/` besides the docs). The GTK path is
  unchanged; 8 new tests.

## Checked here, and what was not

Checked on Linux: 333 vitest tests (contract vs. schema; the checks against real http servers and an https server
with an openssl certificate; core with fakes; the built `ext/core.mjs` as a real process against a fake Neutralino
WebSocket server; the shell page with a fake Neutralino, frame and core; the launcher with a fake process; the build
output; the Neutralino configs' security properties), `tsc --strict`, the menu drift check, the decision-log gate.
**Not checked: a real window with these files.** Each part ran on the Mac in spike 5, never together. The list is in
the README ("Not verified"): the whole window, the frame ↔ shell page conversation with the real web app, HTTPS to a
real server through Node's system CA, the keyboard shortcuts, a killed window.

## Mistakes caught on the way (kept so they are not repeated)

* An extension whose WebSocket cannot be opened got an `error` and no `close` event in Node's WebSocket, so the process
  would never have ended; found by a smoke test of the built bundle, fixed in `extension.ts`, with a test.
* A window closed while the server was only being set up could still start it; guarded in `core.ts`.
* **First run on a real Mac (2026-11-10/11): the window stayed on "Starting…" for ever, for a local and for a given server.**
  Several causes, found one after the other, the second only because the first fix made the core write a log from its first
  line. (1) The core read its app from `CLAUDIA_SHELL_APP`, which Neutralino is not documented to hand on to an
  extension; without it the core threw at its first line, before any log existed. Reproduced by starting the built
  core without the variable. (2) The fix for that, a wrapper script as the extension command, was started (log: "started:
  node v26.13.0") but its stdin ended at once, with no tokens: Neutralino gave the script no auth. Nobody knows why a script
  differs from a direct command here; spike 5 had run `<absolute node> ${NL_PATH}/ext/<file>.mjs`, so that is now the only
  shape used, with app, server and `--use-system-ca` as arguments (`core-command.ts`), set in the config for the run and
  restored after. The page also asks again every second and, after 20 seconds, names the logs and the inspector.
  (3) Still no tokens with the direct command: the likeliest reason is that `parseAuth` required `nlPort` to be a
  number while the spike's extension never checked its type; a stricter check than the peer's data turns every
  message into "nothing arrived". Now tolerant (number or digit string), and the log names the keys and types it got.
  Lessons: *a handshake between two processes needs a timeout that says where to look, and the process that cannot see
  its peer must be able to write down why*; *when a spike proved one exact shape, build exactly that shape and change it
  only when a test on the real thing says so*; pieces that each worked alone are not yet a window.
* The launcher's entry guard and the build tool compare `import.meta.url` with `pathToFileURL(argv[1]).href`: the twins of
  the Windows fixes (CHANGELOG of `clients/windows`), made here from the start.

## The first real window, and an end-to-end check that found a second bug (2026-11-11)

With the token fix the window opened: documents could be created and opened, the native menu appeared (Copy/Paste, the
OS roles, worked), but the web app kept its own menu bar and most native items did nothing. Both are the same symptom:
the web app hides its menu and answers `action` messages only after the shell's `welcome`; no handshake, no native menu.
Which server it was run against decides: the **demo server's web app is a deployed build that may predate web commit
55a9742** (a framed page speaking the contract), and nothing in the shell can change that, because a page that does not
ask never gets answered. To separate that from a bug in the client, the whole local path was run in Chromium: the
built shell page, the real core as a process, the real local server and the real web app, with only Neutralino's client
object faked (scratch harness; not in the repo). Result: handshake, hidden web menu, a native "Save New Checkpoint…"
click opening the web dialog, all working. **The same run showed that the bundled core could not find the server's Python
or the web build** (path counted in levels from the file; fixed with a walk up to the repo root). Without that harness
the next run on the Mac would have shown "needs Python 3.14" for a local server and looked like another startup bug.
Lesson: *run the real components together in whatever environment is at hand before sending them to the one machine
that can run the rest.* Also seen, harmless and the same on Linux (`bridge.py`): the web app reports states for
submenu container ids (`file.manage`, `edit.row`, `edit.column`, `edit.chart`, `edit.image`, `edit.paste-as`), the shell
answers `unknown_action` each time; the web app should not report them, or the contract should say containers are fine.

## Follow-ups

0. Make that Chromium end-to-end run a repo test (it needs Playwright, the built web app and the Python environment, so
   it belongs next to `web/e2e`), and let it also click through the whole menu.

1. **Windows**: the same injection gap very likely exists in `clients/windows`; the same design (D251) applies. Verify on
   the Windows VM first, then port `shell-page.ts` and the core.
2. **A first run on a Mac** (instructions in the README). Expect small fixes; the likeliest places are the frame
   sandbox decision, shortcuts, and what the web app does when `native-menu` removes its own menu bar.
3. **`pick_file`** contract message for the file picker; link handling and `print` from the frame (contract messages).
4. **`sandbox` on the frame**, tried on a Mac.
5. **Design of the shell page's status screens** (starting, connecting, cannot start). They are plain text; per the project
   rule, screen designs come before code, and these were not designed or agreed. An SVG to agree on is owed.
6. **Self-signed certificates** (D245) for all desktop clients, later by the owner's choice.
7. **Packaging and CI**: `.app`, `.dmg`, signing and notarization; a macOS job; also lifting "no spaces in the path" (it comes
   from Neutralino starting the extension with a command line that holds the app folder; an installed bundle has a
   path we control).
8. English-only shell messages (Linux has no catalogs either).
