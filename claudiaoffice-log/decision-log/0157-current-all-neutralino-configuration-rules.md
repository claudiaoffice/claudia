---
id: D157
title: "Proposal: rules for the Neutralino configuration"
status: current
applies-to: all
date: 2026-11-07
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
---

# D157 · Proposal: rules for the Neutralino configuration

**Proposal: rules for the Neutralino configuration.** `tokenSecurity` is `one-time`; the page loads `js/neutralino.js` and **nothing else of Neutralino's** (a second `__neutralino_globals.js` tag clears the token and the window fails with `NE_CL_IVCTOKN`); `none` is never used outside a throw-away development run; the binary and the client library are pinned to the same version, and the checks are re-run on every upgrade; `nativeAllowList` and `filesystemScopes` shrink to what the shell contract uses before E5.11 ships.

**Notes.** The spike's allow-list (`app.*`, `os.*`, `window.*`, `filesystem.*`, `events.*`, `computer.*`, `debug.*`) is deliberately wide. With `none`, any local process or browser tab that finds the port can fetch the token. Client library 6.8.0 lacks `app.getProcessId`, which 6.10.0 has, so the API moves between versions. Wrong guesses on the way (WKWebView, the `neu run` harness, the injection options) are in the notes so they are not tried again. **Built, 2026-11-07 (E5.11):** `macos-client:clients/macos/apps/creates/neutralino.config.json` carries this out — `tokenSecurity: one-time`, binary and client library both pinned to 6.8.0, and `nativeAllowList` trimmed to the four exact methods this client's own page-bridge.ts calls (`app.exit`, `window.setMainMenu`, `window.print`, `events.on`) rather than the spike's namespace wildcards, with `filesystemScopes` left empty (nothing here uses `filesystem.*`). Still a proposal: the owner has not confirmed this specifically, and it has not been re-checked against any Neutralino version past 6.8.0. **Built, 2026-11-08 (E5.11, Windows):** `clients/windows/apps/composes/neutralino.config.json` carries the same rules — `tokenSecurity: one-time`, binary and client library pinned to 6.8.0, `nativeAllowList` trimmed to the same four methods this client's own page-bridge.ts calls. One Windows-only fact added: Neutralino 6.8.0 publishes exactly one Windows binary (`neutralino-win_x64.exe`, no `win_arm64`), so there is no architecture choice to pin here the way there could be on macOS (`arm64`/`x64`). Still not re-checked against a later Neutralino version, on either OS.

*Written as a proposal; confirmed by the owner on 2026-11-10, since the code already follows it.*
