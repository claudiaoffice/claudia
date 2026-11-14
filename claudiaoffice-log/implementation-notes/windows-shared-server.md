# Windows shell on the shared local server (D445, D444, D434)

Branch `win-client`. Written 2026-11-14, built from the decisions and the real server flags: the macOS shell in the
checkout did not have this yet, so this client is the first shell with it and the reference for the Linux and macOS
ones. **Not run on Windows.**

## Symptoms that started it

DevTools opened with every window; the start-up notes of the server appeared in the window ("Starting composes…", then
log lines); the start page did not come. The native menu was right.

## Causes

1. `enableInspector: true` in the three `neutralino.config.json`: Neutralino opens the DevTools window by itself.
   The macOS config has the same flag (not touched here).
2. The core was still on the design before D445: one server per app, random port, `--model`, no idle exit, and the
   server left running when the window closed. A leftover server holds the folder lock (D435); the next start exits
   with code 2 and the core put the tail of the (appended) `server.log` into the window, which showed old runs' notes.
   Unconfirmed that this is why the start page never came; the Windows VM's `server.log`/`shell.log` would show it.

## What the shell does now

* `src/desktop-server.ts` (`DesktopServer`): `ensure` = read the remembered port (`state/desktop-server.json`, written
  exclusively the first time) → `/api/health`: Claudia's and serving this app → use it; other service or port taken →
  new port, state file overwritten; nothing there → start `claudia_server --host 127.0.0.1 --port P --no-tls --dir
  documents --state-dir state --web WEB --exit-when-idle 600`. If that start exits (the lock says someone else was
  first), wait up to 30 s for the winner's server to answer. Version mismatch (server `--version` vs the running one)
  and a server without the app are errors that name the Task Manager, never a takeover.
* `keepPresence`: holds `ws://…/api/presence` while the window is open; on close, `ensure` again (restarts on the same
  port), back-off 1 s → 10 s. `stop()` lets go of the socket and does not stop the server.
* `server.ts`: detached, `unref`, `--exit-when-idle`; failure text quotes the log from the start's own offset.
* `welcome.app` (D444): `contract.ts`, `bridge.ts`; optional in the schema, validated as a token.
* `--debug` switches the inspector on for the run (`setInspector`, restored in `finally`); configs ship with it off.

## Checked

373 unit tests, typecheck, build. An end-to-end run on Linux: three `DesktopServer`s started at once against a stand-in
`claudia_server` with a real `flock` on `DIR/.lock` ended on one port, the two losers logged "another start was first",
the fourth, later window started nothing. Not checked: `msvcrt.locking`, a detached `python.exe` on Windows, `taskkill`.

## Left for the Linux and macOS shells

The same start-up (`DesktopServer` is plain Node and moves over as is), `welcome.app`, `enableInspector` off in the
macOS config, and the per-run restore.
