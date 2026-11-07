# macOS client (E5.11), first slice: Claudia Creates

Written 2026-11-07. What was built for the native macOS client of **creates**, how it was checked, what deviates
from the plan, and how it answers D159 — the question the E0.3 spike (`e0-3-neutralino-windows-macos.md`) left open
rather than resolved. Built on the branch `macos-client`, handed over as a patch (no push access to GitHub from this
session; the owner creates the branch and applies it, her usual workflow for feature branches).

Code: `clients/macos/` (package `claudia-shell-macos`) and `clients/contract/` (the shell contract, unchanged).
Human documentation: `clients/macos/README.md`, also meant for the Sphinx docs once this package has any (it is
plain TypeScript/Node, no Sphinx target set up yet — see "Open points").

## What exists

- `claudia-creates`: a thin Neutralino 6.8.0 shell, application id `de.claudiaoffice.creates`, with the native
  macOS menu bar built from the shared GTK manifest (`manifest.py`'s `describe()`) rather than a second
  hand-written one.
- A **local server started by the Node launcher itself**, not by Neutralino: `launch.ts`'s `prepareServer()` mirrors
  `launch.py`'s `prepare_server()` almost line for line (same two `SetupProblem` messages — missing Python 3.14,
  missing built frontend — same folder-creation-before-start behaviour), adapted for `~/Library/Application
  Support/Claudia` instead of XDG.
- The **D159 decision, built**: the owner chose "loopback, like Linux" over serving Neutralino's own bundle and
  opening a cross-origin WebSocket. `launch.ts`'s `main()` starts the server first (its address has to exist before
  anything else), then starts the Neutralino binary with `--url=<that address>` and `--path=apps/creates` (so
  `neutralino.config.json`'s own `injectGlobals`/`injectClientLibrary`/`injectScript` settings stay in effect for a
  page the binary did not itself serve — unverified; see "Not verified").
- `page-bridge.ts`'s `installBridge()` is the whole adapter the web app needs: it shims
  `window.webkit.messageHandlers.claudia.postMessage` to the exact shape `web/app/lib/shell-bridge.ts`'s
  `detectHandler()` already looks for. **`shell-bridge.ts` itself needed zero changes.** This is D121's "the page
  speaks the contract directly" now covering a second shell the same way it already covers the Linux one.
- `manifest.py` gained a `role` field (D158): the Cocoa editing selector (`undo:`, `redo:`, `cut:`, `copy:`,
  `paste:`) a macOS Edit menu item needs next to its accelerator, or the key does nothing in the web view at all
  (confirmed by the spike, §2 of its notes). Set on the shared Undo/Redo/Copy/Cut/Paste block every app already
  shares; GTK ignores the field. This is the one change made to the *shared* manifest rather than kept local to
  `clients/macos/` — the same reasoning D121 itself gives for not letting shell-specific detail fork the one source
  of truth.
- Checks: `tsc --strict`, vitest (50 tests: identity, paths, server including `freePort()`, menu, page-bridge,
  launch), ruff/ruff-format/mypy clean on the Python side (`generate_menu.py`, 9 pytest tests), a drift guard
  (`npm run check-menu`) between the checked-in `src/generated/menu.*.json` and `manifest.py` itself. No GTK changes
  outside the one `role` field and its matching tests in `clients/linux`.

Nothing in `web/` was changed. Nothing in `clients/linux/` changed except `manifest.py`'s `role` field, its tests,
and its CHANGELOG entry.

## Deviation from the plan

D43 ("desktop clients bundle the frontend, never load it from a remote server") reads, on a literal pass, like it
rules out loading an external loopback URL at all. D115 already qualified this for Linux ("the shell's own local
server serves the bundled frontend, so page and socket share an origin") and D159's own note observes that a
loopback server run by the shell itself arguably still satisfies D43's intent, even though the *page* technically
comes from a URL rather than from files inside the app bundle. This client follows that reading: the frontend is
still the one built into the checkout (or, once packaged, shipped with the app) — the local server just serves it
over loopback instead of the window loading it directly from disk, exactly as Linux already does.

## Mapping to the shared manifest

Unlike the Linux client, which replaced a hand-built "web item it clicks" table with speaking the contract directly
back on 2026-11-05 (D121, see `e5-1-e5-10-menus-and-accessibility.md`), the macOS client was built **after** that
retirement and so never had a `webroutes.json`/`shim.js`-shaped mapping table to begin with — `buildMainMenu()` in
`menu.ts` reads the same seven-menu manifest JSON Linux's own `window.ui` is generated from, one `describe()`, two
consumers. The one macOS-specific rewrite `buildMainMenu()` does is D44's: `help.about` and `file.quit` are pulled
out of Help and File respectively and placed in a new leading application menu titled after the app, because that is
where Cocoa convention (and the spike, §4) put them.

| Native item | Carried out by | Notes |
|---|---|---|
| (App menu) About Claudia Creates | page | `Kind.SHELL` in the manifest (GTK shows a native dialog), forwarded here anyway — macOS has no native About (D158 point 4); `AboutDialog.vue` already exists. |
| (App menu) Quit (Cmd+Q) | shell | `Neutralino.app.exit()` directly; the one click `routeMenuClick()` does not forward to the page. |
| Edit ▸ Undo/Redo/Cut/Copy/Paste | page dispatch **and** Cocoa selector | Both fire on the same click (confirmed in the spike's own `shell.js`: `mainMenuItemClicked` is not short-circuited by also setting a Cocoa `action`) — resolves what looked, on paper, like a conflict between the generic action-dispatch path and the native clipboard commands. |
| Everything else (File/Format/View/Tools/Config) | page | Forwarded as a contract `action` message, same as every other shell. |

## Compatibility notes

1. **No PR_SET_PDEATHSIG equivalent on macOS.** `server.ts`'s top comment names this directly: `stop()` only has
   SIGTERM then SIGKILL, with no kernel-level guarantee the server dies if the shell itself is `kill -9`'d. Linux's
   belt-and-braces signal has no macOS counterpart; not solved here.
2. **The real `claudia_server` package has no `--lifeline`.** Only the spike's own throwaway `testserver.py` had
   one; `buildServerCommand()` matches `composes_command`'s real flags instead.
3. **A separate compiled binary, not an in-process shell.** GTK *is* the Linux shell's own process; Neutralino is a
   binary this launcher has to find (`findNeutralinoBinary()`) and spawn, not something importable. It is not
   checked into the repository (D157: pin the binary and client-library versions together, re-check on every
   upgrade) — `CLAUDIA_NEUTRALINO_BIN` or a conventional `apps/<app>/neutralino-mac_<arch>` path is how a real
   install supplies it.
4. **`injectScript` runs before any `<script type=module>` tag does**, per Neutralino's own docs — `inject-entry.ts`
   is therefore bundled by esbuild into one dependency-free IIFE (`tools/build-inject.mjs`) rather than shipped as
   an ES module.
5. **`enableServer: true` is Neutralino's own documented requirement for loading a remote/external URL at all** —
   it is the native-API/WebSocket channel the injected script's `Neutralino.*` calls depend on; this is not a
   leftover from the spike's config, it was re-confirmed against Neutralino's own "internal CLI arguments" page for
   this client specifically.
6. **`nativeAllowList` trimmed to four exact method names** (`app.exit`, `window.setMainMenu`, `window.print`,
   `events.on`) rather than the spike's wide namespace wildcards (`app.*`, `os.*`, …) — D157 asks for the smallest
   list that works before E5.11 ships; nothing in this client calls `os.*` or `filesystem.*` today, so
   `filesystemScopes` is left empty too.

## First real run (owner, 2026-11-07)

The owner ran `npm ci`, `npm run generate-menu`, `npm run build` and `node dist/launch.js creates` on her own Mac the
same day this slice was handed over. It did not start up, which is expected (no Neutralino binary was placed yet),
but two things it hit were real bugs in this round of the port, not just missing manual setup steps, caught and
fixed before any patch was re-sent:

1. **`npm run generate-menu` failed** with `TypeError: dataclass() got an unexpected keyword argument 'slots'` deep
   inside `manifest.py`. Her `python3` was older than 3.12 (`slots=True` needs 3.10+, but `manifest.py`'s own floor
   is 3.12) — true, but the error gave no hint of that. `generate_menu.py` now checks `sys.version_info` itself
   before importing anything of `manifest.py`'s, and refuses with a message naming the floor and the repository's
   own `uv sync` environment as a 3.12+ interpreter already on hand. This step was never required for `npm run
   build` or `launch.ts` to work — the checked-in `src/generated/menu.*.json` covers that — so it did not block
   her from continuing.
2. **After placing a Neutralino binary** (which `findNeutralinoBinary()`'s own error message, correctly, told her
   was missing) and running again, `node dist/launch.js creates` crashed with an uncaught `ServerStartError: the
   server stopped at start-up (exit code 1)` and a raw Node stack trace — no indication of what actually failed
   inside `claudia_server`. Two real gaps, both now fixed:
   - `LocalServer` never captured the child's stdout/stderr anywhere, so there was nothing to show even if the
     error had been caught. `server.py`'s own `_what_it_said()` — quoting the log's tail in the error message —
     had no Node equivalent in the first round of this port. Fixed: `defaultSpawn()` appends stdout and stderr
     (merged) to `state/server.log`, and `checkReady()`'s `ServerStartError` now quotes its tail.
   - `launch.ts`'s `main()` never caught `server.start()`'s own exceptions, so a clean `ServerStartError` reached
     the console as an uncaught exception instead of a one-line message. Fixed: wrapped in the same
     catch-and-print-the-message pattern every other `SetupProblem` in `main()` already used.

   A third bug was found by trying to reproduce this scenario directly rather than from her transcript: Node's
   `ChildProcess` emits `'error'` (not `'exit'`) when the OS refuses to start a process at all (ENOENT, EACCES);
   nothing listened for it, so it was *fatal and uncaught* regardless of the two fixes above. `LocalServer.spawn()`
   now listens for it and turns it into the same kind of `ServerStartError`.
3. **Separately, re-reading the E0.3 spike's own `run_macos.sh`** while writing this section found that
   `findNeutralinoBinary()`'s default search path was simply wrong: `npx @neutralinojs/neu update` — the actual,
   intended way to fetch the pinned binary — places it in `apps/<app>/bin/`, not in `apps/<app>/` directly as this
   client originally assumed. Fixed before it could cost the owner a second confusing round; the README and the
   "no binary found" message now both name the real command and the real path.

All four fixes have their own tests (`server.test.ts`'s "LocalServer log capture", "defaultSpawn" and "LocalServer
and a spawn that never starts" groups; `launch.test.ts`'s updated `findNeutralinoBinary` test;
`test_generate_menu.py`'s version-guard test) and are in the CHANGELOG's new "Fixed" section. Her transcript still
has not reached the point of actually starting the Neutralino binary — the D159 mechanic below remains exactly as
open as it was.

She also asked, separately, for a one-command way to run this (the README's manual sequence is six steps, several of
them easy to run from the wrong directory), mirroring `start-client.sh`'s existing role for the Linux client. Added
`start-mac-client.sh` at the repository root: `uv sync`, rebuild web and the macOS client every run (same
stale-build lesson `start-client.sh`'s own comment documents, same two independent skip flags), fetch the Neutralino
binary automatically the first time `apps/<app>/bin/neutralino-mac_*` doesn't exist, then `node dist/launch.js
<app>`. Checked in this sandbox as far as it can be without a real Mac or network fetch: an unknown app name fails
cleanly with the right message, and the binary-presence check (missing / already present / `CLAUDIA_NEUTRALINO_BIN`
override) was exercised in isolation for all three branches.

## Not verified (needs a real Mac)

This is the same gap the spike itself named as "the largest gap" and is restated here, now that it has an actual
implementation sitting on top of it rather than just a design question:

1. **Whether `window.Neutralino` exists at all once the window shows the loopback page.** `injectGlobals`,
   `injectClientLibrary` and `injectScript` are confirmed, against Neutralino's own documentation, to be real
   `modes.window` config fields (and `--window-inject-*` CLI flags) that exist for exactly this purpose — but
   whether they actually apply to a page the binary did not itself serve is undocumented and untested, on this spike
   and on this client alike. If they do not, D159 needs its other option: Neutralino serving its own bundle with a
   cross-origin WebSocket to the document server, `--allow-origin` and a fixed port.
2. **The Cocoa-selector-plus-page-dispatch interaction on creates' actual slide editor**, not just the spike's
   generic text field — `lib/clipboard.ts`'s own custom clipboard handling for slides is untested against a native
   Cmd+C/Cmd+V.
3. **No Redo shortcut.** `ROLE_SHORTCUT` in `menu.ts` has no `redo:` entry; nothing in Neutralino's docs or the
   spike confirmed a `shortcut` grammar for Cmd+Shift+Z. The menu item still works by clicking it.
4. **What happens to the server if the Neutralino window is killed outright.** Untested on the spike, and still
   untested here — see compatibility note 1.
5. **A second machine, an older macOS, a screen reader.** Only whatever one Mac the spike ran on.

## Open points for the owner

- **D159 needs the real test it was always going to need**: run this on a Mac and see whether `window.Neutralino`
  exists in the page once the window shows the loopback URL. Everything else in this slice is downstream of that
  answer.
- **Printing** (D158 point 2) is still not wired as a contract message — `Neutralino.window.print()` is typed in
  `NeutralinoLike` but nothing calls it yet.
- **Packaging** (a real `.app`, `.icns` from the existing PNGs, codesigning, notarization, a DMG) is entirely open;
  this slice only produces a runnable `dist/launch.js` against a checkout.
- **Composes and computes** have `identity.ts` entries (`packaged: false`) and generated menu JSON but no
  `apps/<app>/` folder yet — the same "one more entry point" shape Linux's own composes-first slice left for them.
- **No CI job for this package yet** (Linux has one Linux-only job in the main gate); nothing here runs the macOS
  suite automatically today.
