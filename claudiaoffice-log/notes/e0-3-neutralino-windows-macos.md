# E0.3 — Neutralino on Windows 11 and macOS: what was run and what it showed

Written 2026-11-07, at `8648796`. Companion to `e0-shells-and-web-surface.md`, whose paragraph "None of this has been
checked since" this note replaces for the two OSes it covers. The code is `spikes/e0-3-neutralino/`; the raw evidence
is in `spikes/e0-3-neutralino/results/` (four JSON reports).

**Status in one paragraph.** Neutralino 6.8.0 with Plotly 3.7.0 ran on one macOS machine and one Windows 11 machine,
and every automatic check passed on both: shell hello, four Plotly charts (including 100,000 points in WebGL), hover
and relayout events, a bundled font, a font fetched cross-origin from a local server, start and stop of that server,
a native menu from a manifest, and dark/light following the OS. The manual rows that were filled in came out well. One
real defect was found and solved (the token error, below), and three differences between the OSes had to be handled in
the shell (Edit roles on macOS, printing on macOS, the About dialog on both). **This is evidence for a working
Windows/macOS shell, not a decision to ship one**: a clean Windows 10, a screen reader, a maturity check of the
project, the allow-list and — most important — how the real frontend reaches the shell under D115 are all untested.

## What was run

| | macOS | Windows 11 |
|---|---|---|
| Shell | Neutralino 6.8.0, client library 6.8.0 | the same |
| Web view | WKWebView (the system WebKit; UA shows the frozen `AppleWebKit/605.1.15`) | WebView2, Chromium 156 and 157 (Edge UA) |
| Plotly | plotly.js 3.7.0 | plotly.js 3.7.0 |
| WebGL | WebGL 2.0, Apple GPU | WebGL 2.0 over ANGLE/Direct3D 11, Intel Arc Pro |
| Display | 1440×900, devicePixelRatio 2 | 1536×960, devicePixelRatio 2, German locale |
| Colour scheme | followed the OS, seen both dark and light | light |
| macOS version | **not recorded** by the spike (a gap; the report only has the frozen UA) | Windows 11, build not recorded |

One machine per OS, run by the owner. Neutralino was started with `neu run` through the two wrapper scripts
(`run_macos.sh`, `run_windows.cmd`), which also fetch the pinned Plotly and download the Neutralino binaries.

## Automatic checks (the same on both OSes)

All passed on all full reports. Times are the last full run on each OS; the first run on a machine is slower.

| Check | macOS | Windows 11 |
|---|---|---|
| Bar / line / heatmap | 19 / 8 / 25 ms (first run 43 / 11 / 36) | 6 / 6 / 11 ms |
| 100,000 points `scattergl` | 50 ms (**first run 857 ms**) | 43 ms (a later run 103 ms) |
| Hover label drawn, relayout event arrives | yes | yes |
| Local server start, answer `/ping`, stop | 2–5 ms answer | 3 ms answer |
| Font from the bundled page; font from the local server (cross-origin, D26) | both loaded | both loaded |
| Menu from the manifest, native | yes | yes |
| Theme follows the OS | yes (dark and light) | yes |

**The first WebGL run on macOS took 857 ms against 50 ms on the next**: shader and context warm-up. Whatever the real
chart does on first view will include it. Not investigated further.

**Not measured, although the report has a row for it.** The "round-trip time" row of the first reports says
"median 0.0 ms". That ping never left the page's JavaScript, so the number means nothing. It was replaced by a real
native call (`Neutralino.computer.getArch`), but the only report made after that (macOS 15:00) failed on an earlier
attempt that called `app.getProcessId`, which **does not exist in client library 6.8.0** (it exists in 6.10.0; the
client API differs between versions). No report holds a real round-trip time. Install size, cold start and memory were
not measured either; the "start time" row is a by-eye verdict.

## Manual rows, as reported

| Row | macOS | Windows 11 |
|---|---|---|
| Dead keys and AltGr | ok (see the smart-quote note below) | ok (`éèôà€@{`) |
| Input method (Japanese/Chinese) | **not tested** | ok |
| Clipboard, plain and rich text | ok after the fix below (was a problem on the first run) | ok |
| Spellcheck and context menu | ok | ok |
| Drag and drop of text | not filled in | ok |
| Screen reader | not tested | marked not applicable (not tested) |
| Window behaviour, docked panel, start | ok | ok |
| Display scale | ok | ok |
| Native file dialogs; a file name with umlauts saved intact | yes | yes (`D:/claudia-shell-test-äöü.txt`) |
| About dialog | not native: a page dialog, modal, closes on Escape | not native: the same page dialog |
| Printing | browser `window.print()` does **nothing**; via the shell it opens the print dialog | browser `window.print()` works; via the shell also works |
| Python/server left over after quitting | none found | **not reported** |

**The smart-quote note.** The macOS dead-key text came back as `‘ E’e’e è àô€@|`: straight apostrophes in the typed
text became curly quotes. This looks like macOS text substitution applying to editable web content, but it was not
investigated. If `contenteditable` is used for formula entry (E6.3) this matters, because a curly quote is not a
string delimiter. Also not tested: whether the same happens in an `<input>`.

## Findings about Neutralino's behaviour

### 1. The token error `NE_CL_IVCTOKN` and its fix

**Symptom.** On the owner's Mac, and later on Windows 11, the window opened with "NE_CL_IVCTOKN: Neutralino.js
application cannot connect with the framework core using NL_TOKEN". The owner worked around it with
`tokenSecurity: "none"`, which worked, and on Windows had to do the same; the reports from both OSes were made in that
state.

**Cause.** The spike page loaded two script tags: `__neutralino_globals.js` and `js/neutralino.js`. With
`tokenSecurity: "one-time"` the framework sends `NL_TOKEN` once, and the docs say it is "cleared after the first
`authbasic::getToken()`". The framework also writes the `NL_*` globals in front of `js/neutralino.js`. So both files
set the globals, the second assignment overwrote the token with an empty string, and the WebSocket handshake failed.
`NE_CL_IVCTOKN` is the catch-all code raised on any WebSocket `error` event, which is why it says nothing about the
real reason. The owner's reading with injection switched off (`NL_GINJECTED` and `NL_CINJECTED` undefined,
`NL_TOKEN` an empty string) fits this.

**Fix.** Load only `js/neutralino.js`. Confirmed by the owner on macOS and on Windows 11 with `tokenSecurity:
"one-time"` restored. The page keeps a comment above that tag so nobody adds the second one back.
*How sure:* the behaviour changed exactly when the tag was removed, on both OSes; the mechanism of the overwrite is
inferred from the documentation and the observed values, not from reading Neutralino's source.

**Hypotheses that were wrong, so nobody tries them again.** (a) *WKWebView-specific*: it happened on Windows/WebView2
too. (b) *The `neu run` development harness*: starting the binary directly (`direct` mode, below) did not change it.
(c) *The framework's injection settings*: `injectGlobals` and `injectClientLibrary` live under `modes.window`, not at
the top level, and switching them off did not remove the error.

**Why `tokenSecurity: "none"` must not ship.** Without a token any local process, and any browser tab that finds the
port, can obtain the token and call everything in `nativeAllowList` — which in the spike includes `filesystem.*`,
`os.*` and `app.*`. `one-time` works, so there is no reason to use `none` outside a development run.

### 2. Menus

- `setMainMenu` is the window menu on Windows and the **application menu** on macOS. Item fields that matter:
  `id`, `text`, `isDisabled`, `isChecked`, `menuItems`, `shortcut`, `action`.
- **On macOS, an Edit menu whose items only send events does not work for the clipboard**: Cmd+C and Cmd+V did
  nothing, because the web view only receives them if the menu item carries the Cocoa selector. Each Edit item needs
  `action` set to `undo:`, `redo:`, `cut:`, `copy:`, `paste:`, `selectAll:` and a `shortcut`. With that, the owner
  confirmed the clipboard including rich text.
- `shortcut` is a real accelerator on macOS and display-only on Windows (the web page still has to handle the key).
- On Windows no Cocoa actions exist; the Edit items worked through `document.execCommand` in the page. Events seen:
  `edit.copy`, `edit.selectall`, `edit.paste`.
- The spike's manifest therefore carries a `role` and an `accel` per Edit item, and the shell maps them
  (`rolesNative` is true on macOS, false on Windows). The Linux shell has the same idea (`webpage.py` calls
  `execute_editing_command`). **The Linux manifest (`manifest.py`) has accelerators in GTK
  syntax (`<Primary>n`) but no role field, and the v1 contract has no print method** — see D158.

### 3. Printing

The macOS WKWebView does not implement `window.print()`; the call returns and nothing happens. Neutralino has
`Neutralino.window.print()`, which opens the OS print dialog on macOS and works on Windows too. Printing is therefore
a **shell service** (a `window.print` method on the contract), not something the page can assume. The GTK half of the older
spike did the same with `WebKit.PrintOperation`; the real Linux shell has no print method yet.

### 4. About

`nativeAbout` is false on both OSes: Neutralino offers no native About panel, so the page shows its own modal dialog,
which the owner found modal and closable with Escape. `web/app/components/AboutDialog.vue` exists and is opened from
the web menu in all three apps, so no new component is needed — but `help.about` must not be swallowed by the shell
on these OSes. (The macOS convention is an About item in the application menu; it would simply send the same action.)

### 5. API surface and versions

- Client library 6.8.0 has no `app.getProcessId`; the spike's first ping used it and failed. **Pin the binary and
  client versions together** (the config has `cli.binaryVersion` and `cli.clientVersion`, both 6.8.0) and re-run the
  checks on every upgrade.
- `neu run` starts the binary with `--load-dir-res --path=. --export-auth-info --neu-dev-extension` and, with
  `--neu-dev-auto-reload`, for a watch loop. Starting the binary yourself (`bin\neutralino-win_x64.exe --load-dir-res
  --path=.` or `neutralino-mac_arm64`/`mac_x64`) is what the wrappers call `direct`; on Windows the owner confirmed from
  the command line that the dev extension was then **not** started, yet developer tools still opened (the spike
  enables the inspector).
- The developer tools request `/.well-known/appspecific/com.chrome.devtools.json`; Neutralino answers 404 and the
  Windows console prints an error. Harmless.
- Binary names: `neutralino-win_x64.exe`, `neutralino-mac_arm64`, `neutralino-mac_x64` (and the Linux ones, not used).

### 6. Server lifetime

`Neutralino.os.spawnProcess` starts the Python test server with the lifeline idea of E0.2 (`--lifeline`: the server
exits when its stdin closes); on stop the shell sends the stdin-end event and then exits the process. The spike tries
`uv run --no-project python`, then `py -3`/`python3`, then `python`. On macOS no process was left over. **No Windows
leftover check was reported.** What happens when the Neutralino window is killed rather than closed is untested on
both. The Linux shell uses a process group plus `PR_SET_PDEATHSIG` (D119); whether Neutralino offers anything equivalent was
not looked at.

### 7. Files and fonts

File open/save dialogs are the native ones on both OSes and wrote umlaut file names and content correctly. A font
bundled with the page and a font served from the local server (a different origin) both loaded; the second needs the
server to send `Access-Control-Allow-Origin`.

## Open: how the real frontend reaches a Neutralino shell (this is the largest gap)

The spike's page is **Neutralino's own bundled page**, which Neutralino serves and to which it injects its API. The
real design is different. D115 has the Linux shell load the frontend **from the document server's own loopback
server**, so that page and WebSocket share one origin and no `--allow-origin` is needed; the web app speaks the shell
contract itself (D121, `web/app/lib/shell-bridge.ts`). For Neutralino there are two ways and nothing is tested:

1. **Neutralino serves the bundled frontend** (D43 as originally written) and the page opens a WebSocket **across
   origins** to the document server, which then needs `--allow-origin` for Neutralino's origin, and Neutralino's port
   must be fixed or the origin changes every start (and `localStorage` with it — the same side effect D115 accepted
   for Linux). The spike's cross-origin font fetch shows cross-origin fetches work; a cross-origin WebSocket from this
   shell was not exercised.
2. **Neutralino's window points at the document server's loopback URL**, as on Linux. Neutralino's API then sees an
   external page: the globals and client library would have to be injected into it (`modes.window.injectGlobals`,
   `injectClientLibrary`), and what the token model does for such a page is unknown. This keeps one origin, and the
   web app's contract client would talk to a thin adapter in the page.

Either way the web app's shell bridge needs a **Neutralino transport**: today it speaks to the GTK shell through a
WebKit script message handler. That is a question for the design, not for another spike of the same kind; D159 records
it as open.

## What was not tested

- A **clean Windows 10 22H2** (WebView2 present or not, the Evergreen runtime installer). The E0.3 acceptance
  criterion asks for it. Nothing here covers it.
- **GNOME on Wayland**, input methods and portals on Linux (unchanged from before; the Linux shell was run headless).
- **Screen readers** on all three (VoiceOver, NVDA, Orca). E0.8 stays open on this.
- An older macOS; the version used was not recorded.
- A **maturity check** of Neutralino (release rhythm, number of maintainers, open issues about Wayland, IME and
  accessibility). Not done; the earlier claim that it is one maintainer's project is still a guess.
- The **allow-list** (`app.*`, `os.*`, `window.*`, `filesystem.*`, `events.*`, `computer.*`, `debug.*` in the spike) and
  `filesystemScopes`: the spike is permissive on purpose; the real shell needs the smallest list that works.
- **Plotly in the real frontend.** The web app has no chart. The Plotly page is a stand-in, so the criterion that
  motivated D41/D42 (a Plotly chart in the real UI on every OS) is still untested.
- Real-time **round-trip** cost of the shell bridge, install size, cold start, memory.
- Signing and notarisation on macOS; installers on both.

## Fallbacks if Neutralino disappoints

Unchanged from the earlier note; nothing found so far argues for them. **pywebview 6.2.1** (BSD; WebView2 through
pythonnet, WKWebView through PyObjC; menus exist, shortcuts not yet; its Linux backend is GTK 3), **Tauri 2/wry**
(Rust, mature; GTK 3 `webkit2gtk-4.1` on Linux), **webview/webview** (C, minimal), or a small native shell per OS. The
adapter stays thin (D42) so the switch costs one transport and one menu mapper.

## The spike package

`spikes/e0-3-neutralino/` — see its README. It contains only the Neutralino half of the older `e0-3-shells`
spike (the GTK half became `clients/linux/`). Its page speaks a spike-only request/response bridge, **not** the v1
contract in `clients/contract/`; nothing in `clients/` or `web/` was changed.
