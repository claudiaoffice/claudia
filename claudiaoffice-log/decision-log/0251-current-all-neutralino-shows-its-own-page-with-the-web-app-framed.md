---
id: D251
title: "Neutralino shows its own page, and the web app is framed in it; the native parts run in an extension"
status: current
applies-to: all
date: 2026-11-10
round: "E5.11 macOS client: three apps, command line, server flow"
supersedes: [D159]
superseded-by: []
---

# D251 · Neutralino shows its own page, and the web app is framed in it; the native parts run in an extension

**A Neutralino window shows a static page that Neutralino itself serves (`apps/<app>/index.html`: it loads `js/neutralino.js` and nothing else of Neutralino's, D157, and starts it with `Neutralino.init()`), and that page shows the Claudia web app (this computer's server, or a remote one, http or https) in a full-window `<iframe>`.** The shell page builds the native menu and speaks the shell contract with the web app by `postMessage` (the page accepts a message only from its own frame and only from the origin it opened; the web app accepts one only from its parent and only if that is a loopback page). Everything that is not drawing — the checks of a server, the server list, the settings, the life of the local server — is a Node **extension** that Neutralino starts with the window and ends with it; page and extension talk through `Neutralino.extensions.dispatch` and `app.broadcast`. The Neutralino configuration keeps `tokenSecurity: one-time` (never `none`, D157), no `inject*` settings, and an allow-list without `filesystem.*`, `os.*` or `computer.*`.

**Notes.** *Why D159 had to go.* On a page that Neutralino did not serve, the one-time token is empty and `init()` is never called, so no API call can be made from it; `tokenSecurity: none` does not help either (`NE_CL_IVCTOKN` with it too). Four spikes on the owner's Mac (2026-11-10) showed this for http and https pages and with an `.app` bundle; a fifth proved the design above: shell page with token, native menu, a frame of an https page (`example.com`, `demo.claudia-office.de`), a page-to-extension-to-page round trip. The earlier demo's own console agreed: its native channel had never worked, and the "native menu" seen in it was the web app's own. *Kept from D159:* the web app is the same everywhere and needs no second contract client; the local server is started by the shell. *Security:* a cross-origin frame cannot reach the shell page's `Neutralino` object or token (`SecurityError`) and cannot open Neutralino's WebSocket without the token; Neutralino's static server serves the app folder, which holds code and no secret. The frame has no `sandbox` attribute yet (not tried on a Mac; a follow-up). *Consequences:* the native menu now replaces the web app's menu bar on macOS (`native-menu` in `welcome`), a visible change against the demo; `<input type="file">` in WKWebView still opens no panel and needs a contract message (`pick_file`) because the old in-page workaround cannot run in a frame; links that open windows and `window.print()` from the frame are not handled yet. **Windows:** `clients/windows` was built on D159 and very likely has the same gap (unverified); the same design applies there and is a follow-up, not part of this decision's first build.
