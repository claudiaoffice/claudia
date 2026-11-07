# Claudia for macOS (claudia-shell-macos)

The native client of Claudia for macOS: a thin Neutralino shell around the one web frontend (D42–D44), the same
discipline the Linux client (`clients/linux/`) follows for GTK. Today it contains **Claudia Creates**; composes and
computes follow the same way Linux's did (one more entry in `identity.ts`, one more `apps/<app>/`).

**D159's core mechanic is confirmed (owner's own Mac, 2026-11-07): `window.Neutralino` exists and works on the
loopback page.** The native menu, the dock icon, and the whole D159 option-2 adapter came up as designed on the
first real run past the start-up bugs (see the CHANGELOG and the implementation notes for the three further bugs
that first real run found and fixed: the application-menu heading, the window-title casing, and Insert Image's
file picker). What's below "Not verified" is everything past that boundary — still this client's best-effort
answer, not yet checked on a real Mac.

```
clients/
  contract/            the shell contract: JSON schema, versioned, shared by every shell (see its README)
  macos/
    src/
      identity.ts       which app, its bundle id, title, server model          (plain Node)
      paths.ts           ~/Library/Application Support/Claudia, frontend/python lookup (plain Node)
      server.ts          start, wait for and stop the local server, freePort() (plain Node)
      menu.ts            the shared GTK manifest -> Neutralino WindowMenuItem  (plain TS)
      page-bridge.ts      D159 option 2: shims window.webkit.messageHandlers   (plain TS; a few real Neutralino calls in installBridge())
      file-dialog.ts      swaps a broken <input type="file"> click for Neutralino's own Open dialog (plain TS; a few real Neutralino/DOM calls in installFileDialogBridge())
      inject-entry.ts    the file Neutralino's injectScript actually loads     (bundled, not run directly)
      launch.ts          prepare the server, find the binary, start both       (Node + child_process)
      app-bundle.ts      wraps the binary in the smallest .app that gets CFBundleName to apply (plain Node, fs only)
      generated/         menu.<app>.json, checked in, generated from manifest.py
    tools/
      generate_menu.py   imports clients/linux's manifest.py (no GTK) and writes generated/menu.<app>.json
      build-inject.mjs   esbuild: bundles inject-entry.ts into apps/<app>/inject/claudia-bridge.js
    apps/creates/
      neutralino.config.json, icon.svg/png, inject/claudia-bridge.js (built by npm run build, not checked in),
      bin/neutralino-mac_<arch> (downloaded by npx @neutralinojs/neu update, not checked in either)
    tests/
```

## Running it from a checkout

```
uv sync                                    # the server's Python 3.14 environment: .venv
(cd web && npm ci && npm run build)        # the web frontend: web/.output/public
cd clients/macos && npm ci
npm run generate-menu                      # regenerate src/generated/menu.*.json from the shared manifest --
                                            # needs Python 3.12+ on PATH as `python3` (see note below)
npm run build                              # tsc, then bundles apps/creates/inject/claudia-bridge.js
(cd apps/creates && npx @neutralinojs/neu update)   # downloads the pinned binary into apps/creates/bin/
node dist/launch.js creates
```

Or, from the repository root, `./start-mac-client.sh` does all of the above for you in one go (including fetching
the Neutralino binary if it's missing) -- see its own comments for the `CLAUDIA_SKIP_WEB_BUILD`/
`CLAUDIA_SKIP_MACOS_BUILD` escape hatches, and `./start-client.sh` for the Linux equivalent.

**`npm run generate-menu` needs a `python3` that is 3.12 or newer**, because it imports the shared manifest
(`clients/linux/src/claudia_shell_gtk/manifest.py`), which uses `@dataclass(slots=True)`. macOS's own system
`python3` is often older than that (3.9 on some installs) and gives a confusing `TypeError: dataclass() got an
unexpected keyword argument 'slots'` many frames deep inside `manifest.py` if it is used — this script checks the
version itself first and refuses with a clear message instead, naming the repository's own `uv sync` environment
(`../../.venv/bin/python3`) as a 3.12+ interpreter that is already there. This step is not strictly required to
build or run the client — the checked-in `src/generated/menu.*.json` is used either way — it only needs to be run
again after an edit to the shared manifest.

**The Neutralino binary is not checked into the repository** (D157: pin it to the same version as the client
library, 6.8.0 today). `npx @neutralinojs/neu update`, run from inside `apps/<app>/` (where that app's own
`neutralino.config.json` lives), reads `cli.binaryVersion` from it and downloads the matching binary into a `bin/`
subdirectory it creates there — `apps/creates/bin/neutralino-mac_arm64` or `neutralino-mac_x64`, confirmed against
the E0.3 spike's own `run_macos.sh`. `launch.ts` looks there by default; if a binary already exists somewhere else,
point `CLAUDIA_NEUTRALINO_BIN` at it instead.

Documents are kept in `~/Library/Application Support/Claudia/creates/documents` and the server's state — including
**`server.log`**, the first place to look if `node dist/launch.js creates` reports `ServerStartError` — in the
sibling `state/` folder. There is no packaged `.app` yet (icon assets exist as PNG; `.icns`, codesigning and
notarization are not done — see "Not done").

| Variable | Meaning |
| --- | --- |
| `CLAUDIA_SERVER_PYTHON` | The Python 3.14 that runs the server. Default: `.venv/bin/python` of the checkout. |
| `CLAUDIA_WEB_DIR` | The built web frontend. Default: `web/.output/public` of the checkout (nothing ships a packaged copy yet). If set, it is the only candidate: a wrong path is reported, not replaced. |
| `CLAUDIA_NEUTRALINO_BIN` | The compiled Neutralino binary. Default: `bin/neutralino-mac_<arch>` under `apps/<app>/`, where `npx @neutralinojs/neu update` places it; not checked into the repo. |

If the server itself fails to start, `launch.ts` now quotes the end of `server.log` in the error message instead of
just the bare exit code — a missing `claudia_server` package, a bad `--model`, or anything else the server printed
on its way out shows up directly on the console.

## How it works

* **The server, started by this launcher, not by Neutralino.** `launch.ts` spawns `<server python> -m claudia_server
  --model claudia_creates:SlideModel --host 127.0.0.1 --port <free port> --no-tls --web <frontend> ...` itself (plain
  `node:child_process`, mirroring `server.py`/`launch.py` on Linux) and waits for `/api/health`, **before** the
  Neutralino binary is started at all — the server's address has to exist first, because it becomes the `--url` the
  shell is pointed at.
* **D159 option 2: the window loads that address, not anything Neutralino ships.** The binary runs as
  `claudia-creates --path=apps/creates --url=http://127.0.0.1:<port> --enable-server=true`. `--path` keeps
  `neutralino.config.json` (and its `injectGlobals`/`injectClientLibrary`/`injectScript` settings) in effect; `--url`
  overrides what the window actually shows. `--enable-server=true` is Neutralino's own documented requirement for
  loading a remote/external URL — it is the native-API/WebSocket channel the injected script depends on.
* **The injected script (`inject-entry.ts`, bundled to `apps/creates/inject/claudia-bridge.js`) is the whole
  adapter.** It shims `window.webkit.messageHandlers.claudia.postMessage` to look exactly like the WebKitGTK handler
  `web/app/lib/shell-bridge.ts`'s own `detectHandler()` already looks for — so **the web app needs zero changes** for
  a second shell, the same way D121 put the contract client directly in the page for the first one. It answers
  `hello` with `welcome` itself (there is no separate native shell process to round-trip to: this script *is* the
  shell, running inside the page), builds the native menu from the generated manifest JSON, and turns
  `mainMenuItemClicked` into contract `action` messages.
* **The shared menu manifest, one more consumer.** `manifest.py` (`clients/linux/src/claudia_shell_gtk/manifest.py`)
  stays the one source of truth for File/Edit/Format/View/Tools/Config/Help across every app and shell; `role` (the
  Cocoa selector D158 needs — `undo:`, `redo:`, `cut:`, `copy:`, `paste:`) was added to it rather than duplicated
  here. `generate_menu.py` imports it (no GTK, by the same discipline `manifest.py` was already built to) and writes
  `src/generated/menu.<app>.json`; `menu.ts` turns that into Neutralino's `WindowMenuItem[]`, relocating `help.about`
  and `file.quit` into a leading application menu (D44) and mapping each Edit role to its Cocoa selector and
  `ROLE_SHORTCUT` accelerator.
* **Quit is native; About is not.** `page-bridge.ts`'s `routeMenuClick()` sends `file.quit` straight to
  `Neutralino.app.exit()`. `help.about` is `Kind.SHELL` in the manifest (GTK shows its own dialog for it), but
  Neutralino has no native About panel (D158 point 4), so it is forwarded to the page like any other action —
  `AboutDialog.vue` already exists and needs no change.
* **The downloaded binary runs from inside a minimal `.app` bundle, not directly.** The application-menu heading
  (next to the Apple logo), the Cmd+Tab switcher and Activity Monitor all read a running process's *bundle*
  identity (`CFBundleName`) when it has one, not anything Neutralino's own `NSApplication.setMainMenu:` call sets
  (confirmed by reading its macOS source) and not `argv0` either (confirmed against outside reports of the same
  gap in other bare-executable Cocoa apps). `app-bundle.ts`'s `ensureAppBundle()` builds
  `apps/<app>/bin/claudia-<app>.app/Contents/{MacOS/claudia-<app>,Info.plist}` — a copy of the downloaded binary
  plus the smallest Info.plist that gets `CFBundleName` to apply — and `launch.ts` spawns that instead. No `.icns`,
  no codesigning, no notarization (still "Not done"); `--path` keeps pointing at `apps/<app>/` regardless of where
  the binary itself runs from (confirmed against Neutralino's own `settings.cpp`).
* **`<input type="file">` gets the same zero-change-to-the-web-app treatment.** WKWebView (the engine Neutralino's
  macOS binary embeds) shows no native Open panel for a file input unless the host app implements a WKUIDelegate
  method for it, which this generic binary does not — confirmed on the owner's own Mac, where clicking "Choose a
  file…" did nothing at all. `file-dialog.ts`'s `installFileDialogBridge()` intercepts the click in a capture-phase
  listener, runs `Neutralino.os.showOpenDialog()` and `filesystem.readBinaryFile()` instead, and hands the result
  back to the input as an ordinary `File` via `DataTransfer` — `ImageImportDialog.vue`'s own `onFileChange` runs
  exactly as it would for a real OS dialog, with no changes of its own.

## Tests

```
cd clients/macos
npm test              # vitest: identity, paths, server (incl. freePort, log capture), menu, page-bridge, launch, file-dialog, app-bundle — 79 tests
npm run typecheck      # tsc --strict over src/ and tests/
python3 -m pytest tools/tests   # generate_menu.py: 10 tests
ruff check . && ruff format --check . && mypy tools
npm run check-menu     # fails if src/generated/menu.*.json has drifted from manifest.py
```

Nothing here starts a real Neutralino binary or opens a real window — `installBridge()` in `page-bridge.ts` and
`installFileDialogBridge()` in `file-dialog.ts` are the two functions with no test of their own, because what they
call only exists once `window.Neutralino` is real (and, for the latter, a real DOM — `vitest.config.ts` runs this
package's tests under Node, not jsdom). Everything pure around them (`routeMenuClick`, `applyActionStates`,
`nextCheckedTarget`, the whole of `menu.ts`, and `file-dialog.ts`'s `parseAcceptExtensions`/`guessMimeType`/
`basename`) is tested without one.

## Not verified (needs a real Mac)

1. ~~D159's core mechanic.~~ **Confirmed, 2026-11-07**: `injectGlobals`/`injectClientLibrary`/`injectScript` do
   reach the loopback page; `window.Neutralino` exists, the native menu renders, and the dock shows this app's own
   icon.
2. **The dual native-Cocoa-action-plus-page-dispatch interaction** for creates' own `lib/clipboard.ts` on a real
   slide canvas — the spike only confirmed this on a generic text field, not Creates' editor.
3. **No Redo shortcut.** `ROLE_SHORTCUT` in `menu.ts` has no `redo:` entry; no confirmed Neutralino grammar for
   Cmd+Shift+Z was found. Redo still works by clicking the menu item.
4. **Orphaned server processes.** No PDEATHSIG equivalent on macOS and no `--lifeline` flag in the real
   `claudia_server` package (unlike the spike's own throwaway `testserver.py`), so `stop()` only has SIGTERM/SIGKILL
   — what happens to the server if the Neutralino window is killed outright, rather than closed, is untested.
5. **A clean machine.** Only whatever Mac the E0.3 spike ran on; no second Mac, no older macOS, no screen reader.

## Not done

Packaging (a real `.app` bundle, `.icns`, codesigning, notarization, a DMG or installer); composes and computes (only
`creates` has an `apps/<app>/` folder — `packaged: false` in `identity.ts` for the other two); printing as a contract
message (D158 point 2 — `Neutralino.window.print()` exists and is in `NeutralinoLike`, but nothing calls it yet);
`nativeAllowList`/`filesystemScopes` are trimmed to the six methods this client actually calls today
(`app.exit`, `window.setMainMenu`, `window.print`, `events.on`, `os.showOpenDialog`, `filesystem.readBinaryFile`)
but have not been re-checked against a later
Neutralino upgrade (D157 asks for that on every version bump); translations; single-instance behaviour.
