---
id: D506
title: "The macOS window's close button ends the app through the shell page, not through Neutralino's exitProcessOnClose"
status: current
applies-to: all
date: 2026-11-15
round: "The three desktop clients: one server, files, printing (branch clients)"
supersedes: []
superseded-by: []
---

# D506 · The macOS window's close button ends the app through the shell page, not through Neutralino's exitProcessOnClose

**In the three `clients/macos/apps/<app>/neutralino.config.json`, `modes.window.exitProcessOnClose` is `false`. The
shell page listens for Neutralino's `windowClose` event, first of all its listeners, and ends the app with
`Neutralino.app.exit()`, the same call as Quit (Cmd+Q). Closing the window and quitting are one path.**

**Notes.** With `exitProcessOnClose: true`, every click on the close button crashed the app (CODE-26): Neutralino
6.8.0's `windowShouldClose:` handler calls `app::exit()` → `window::_close()` on the main thread, and `_close()` does
`dispatch_sync(dispatch_get_main_queue(), …)`, which libdispatch traps when the caller already owns the main queue
("dispatch_sync called on queue already owned by current thread"). Neutralino's main branch of 2026-10-29 still has the
same code, so an upgrade does not fix it. `app.exit` from the page arrives on Neutralino's server thread, from which
the `dispatch_sync` is allowed; that is why Quit never crashed.

The listener is registered before the native menu is set and before the core is asked to start, so a window that is
still starting can be closed. One gap remains: if the page's script never runs at all, the close button does nothing
(Neutralino only sends the event), and the app has to be ended with Force Quit. A fix in
Neutralino itself (run the block directly when already on the main thread) would close that gap and is worth
reporting upstream; when a fixed version is pinned (D157), this decision can be superseded and the flag set back.
Windows and Linux are not affected (the `dispatch_sync` is macOS-only; Linux has no Neutralino) and keep their
configuration.

*Proposed in chat on 2026-11-15 together with the fix; the owner asked for the patch.*
