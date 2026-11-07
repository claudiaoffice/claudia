# E0.3 spike — Neutralino shell on Windows and macOS

A throwaway test bench, not product code. It answers one question from the backlog (E0.3, E0.8): **does a Neutralino
window around the OS web view run Claudia-style web content — Plotly charts, native menus, file dialogs, a bundled
server process — on Windows 11 and macOS?** The findings are in
`claudiaoffice-log/notes/e0-3-neutralino-windows-macos.md`; the raw evidence is in `results/`.

Status at `8648796` + this change: run once on macOS and once on Windows 11 by the owner, all automatic checks
passing. **Not run** on Windows 10, with a screen reader, or against the real frontend.

## What it is not

* It is not `clients/` and does not use the v1 contract in `clients/contract/`. The page talks to Neutralino through a
  small request/response bridge in `page/shell.js` (`hello`, `ping`, `menu.set`, `file.open`, `file.save`,
  `about.show`, `window.print`, `theme.get`, `server.start/stop`, `report.write`, `app.quit`), written for the spike.
* It does not contain the web app. The page is a plain HTML test page with bundled Plotly.
* Its GTK counterpart is gone: the Linux half of the older spike became `clients/linux/`.

## Run it

You need Node.js (for `npx @neutralinojs/neu` and to fetch Plotly) and, for the server rows, Python 3.12 or newer
(or `uv`). Nothing is installed globally.

* **Windows:** double-click `neutralino\run_windows.cmd`, or run it from a terminal.
* **macOS:** `sh neutralino/run_macos.sh`

Both scripts fetch plotly.js (pinned, see `fetch-vendor.mjs`; the file is git-ignored), copy `page/` and `server/` next
to the config, download the Neutralino binaries on the first run, and start the app. Add the word `direct` to start the
binary yourself instead of through `neu run`, which was useful for ruling out the development harness.

In the window: the automatic checks run on load and fill a table; the manual rows ask you to try things (type with
dead keys, paste rich text, drag text, open the print dialog, …) and mark them ok / problem / n/a. **Save report…**
opens a save dialog for `e0-3-neutralino-<OS>-<date>.json`; copy it into `results/`. The `?selftest` query only runs
the automatic checks; a Neutralino shell cannot write the report by itself (`report.write` is not implemented there), so
the button is the way.

## Rules learned the hard way

1. **Load only `js/neutralino.js`.** Do not also load `__neutralino_globals.js`. Under `tokenSecurity: "one-time"` the
   second tag overwrites the token with an empty string and the window fails with `NE_CL_IVCTOKN`. `index.html` has a
   comment saying so.
2. **`tokenSecurity` stays `"one-time"`.** `"none"` made the early runs work only because of the duplicate-tag bug, and
   it lets any local process fetch the token. The first reports in `results/` were made with `"none"`; the reports do
   not record it.
3. **Pin the client library to the binary** (`cli.binaryVersion`, `cli.clientVersion`). The API differs between 6.8.0
   and 6.10.0.
4. **Edit menu items on macOS need `action` (Cocoa selector) and `shortcut`**, or the clipboard keys do nothing.
5. **Printing goes through `Neutralino.window.print()`**; the macOS web view has no `window.print()`.

## Files

| Path | What |
|---|---|
| `page/` | the test page: `index.html`, `app.js` (checks, charts, report), `shell.js` (the bridge), `manifest.js` (menu manifest with roles and accelerators), `style.css`, a bundled test font |
| `server/testserver.py` | a stand-in for a document server: `/ping`, a font, and `--lifeline` (exits when stdin closes). Standard library only; checked with the repo's ruff |
| `neutralino/` | `neutralino.config.json`, the two wrapper scripts, `.gitignore` for the downloaded binaries |
| `fetch-vendor.mjs` | downloads the pinned plotly.js into `page/vendor/` |
| `results/` | the four reports behind the findings note, see below |
| `results-template/` | the sheet for the manual rows when a report cannot be saved |

## Reports in `results/`

| File | Machine | Notes |
|---|---|---|
| `…-Darwin-2026-11-07-14-43.json` | macOS | the full run; its clipboard row says "problem" (the Edit-role fix came after) |
| `…-Darwin-2026-11-07-15-00.json` | macOS | the real-ping attempt that failed on a missing `app.getProcessId` in client library 6.8.0 |
| `…-Windows-2026-11-07-14-39.json` | Windows 11 | the full run with the first version of the page |
| `…-Windows-2026-11-07-14-50.json` | Windows 11 | the run that exercised the Edit items and printing through the shell |

All four were produced with `tokenSecurity: "none"`. A partial macOS report (14:58, nearly empty) was left out.
