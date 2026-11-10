---
id: D159
title: "The owner chose, by explicit answer (`AskUserQuestion`, 2026-11-07): Neutralino's window points at the document server's own loopback URL, like Linux's…"
status: current
applies-to: all
date: 2026-11-07
round: "Neutralino on Windows and macOS (twenty-eighth round)"
supersedes: []
superseded-by: []
---

# D159 · The owner chose, by explicit answer (`AskUserQuestion`, 2026-11-07): Neutralino's window points at the document server's own loopback URL, like Linux's…

**The owner chose, by explicit answer (`AskUserQuestion`, 2026-11-07): Neutralino's window points at the document server's own loopback URL, like Linux's shell (D115), and Neutralino's API is injected into that external page** — over serving Neutralino's own bundle and opening a cross-origin WebSocket to the server. Built on the unmerged `macos-client` branch as `macos-client:clients/macos/src/launch.ts` (starts the local server first, then the Neutralino binary with `--url=<that address> --path=apps/<app>`) and `macos-client:clients/macos/src/page-bridge.ts` (shims `window.webkit.messageHandlers.claudia` so `web/app/lib/shell-bridge.ts` needs no change at all — D121's "the page speaks the contract directly" now covers a second shell).

**Notes.** No longer a proposal — this was the owner's explicit choice, not Claude's suggestion left unconfirmed. Against Neutralino's own documentation (not the spike, which exercised neither option): `modes.window.injectGlobals`/`injectClientLibrary`/`injectScript` and the matching `--window-inject-*`/`--url`/`--path`/`--enable-server` CLI flags are real and documented for exactly this purpose. D43 is read the way D115 already reads it for Linux: the frontend shown is still the one built for/bundled with the app; the local server merely serves it over loopback instead of the window loading it from disk. **Confirmed, 2026-11-07 (owner's own Mac):** `window.Neutralino` does exist on the loopback page — the native menu rendered and the dock showed creates' own icon. The one thing that was still open (whether Neutralino's injection reaches a page it did not itself serve) is closed; see `notes/e5-11-macos-client.md`'s "Second run" section for the three further bugs that run found and fixed (application-menu heading, window-title casing, Insert Image's file picker). **Carried to Windows, 2026-11-08 (E5.11):** the same loopback-URL/injected-API option, built as `clients/windows/src/launch.ts` + `page-bridge.ts`, structurally identical to the macOS pair. Not re-asked as a platform-specific question — the decision was "how a Neutralino shell reaches the frontend", not "how a *macOS* Neutralino shell reaches it" (the owner's own framing when confirming this scope for Windows), and nothing in the spike or the macOS build found an OS split in the answer. **Not yet confirmed on a real Windows machine** — unlike the Mac run above, nobody has run this build on Windows yet; see `notes/e5-11-windows-client.md`.
