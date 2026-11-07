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
