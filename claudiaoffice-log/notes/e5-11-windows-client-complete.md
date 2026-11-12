# Windows client (E5.11), complete: three apps, command line, server flow, on D251

Written 2026-11-11 on the branch `win-client-complete` (created by the owner; handed over as patches, no push access
from this session). Scope as asked: bring the Windows client to what Linux and macOS now do (all three apps, the remote
server flow with HTTPS), with the same command-line parameters. Decisions: **D271** (follows D251, same CLI and server
flow), **D272** (process-tree stop, a proposal). Code: `clients/windows/`; `web/app/lib/shell-bridge.ts`,
`web/e2e/` and the contract README carried over from `macos-client-complete` unchanged. Read
`e5-11-macos-client-complete.md` first: it holds the spikes and the reasoning for D251, which are not repeated here.

## Method

The macOS branch was read as the reference and its design was ported, not re-derived. Shared files (web side,
contract README, D251, D159's superseded rename) were copied verbatim so the later merge has one version of each.
Platform code was adapted file by file; the tests were adapted with it, then the Windows-only behaviour got tests of
its own. Nothing was run on Windows. The old `[unreleased]` fixes (build-inject, entry guard, `windowsHide`) are
covered by the new code or kept.

## What differs from macOS, and why

| Topic | Windows | Reason |
|---|---|---|
| Extension command | `commandWindows` in `neutralino.config.json` | Neutralino's per-OS key |
| Binary | `neutralino-win_x64.exe` | the only Windows build of 6.8.0 |
| Menu | no application menu, no Cocoa roles, Quit in File | D44, D158 |
| Data dir, Python | `%LOCALAPPDATA%\Claudia\<app>`, `.venv\Scripts\python.exe` | Windows convention, uv layout |
| Stop the server | `taskkill /pid N /T /F`, fallback `kill()` | venv launcher stub spawns the real interpreter (D272) |
| Environment | set/remove variables case-insensitively | `Path` vs `PATH` — a lookup of `PATH` in an object copied from `process.env` misses on Windows |
| Node path with spaces | 8.3 short name via `cmd /c for %I … %~sI`, else plain `node`, with a console note | Neutralino splits the extension command at spaces; `C:\Program Files\nodejs\node.exe` breaks it |
| Console | `windowsHide: true` on every spawned child | a console window would flash for server and core |
| Close signal | `SIGHUP` forwarded as well as `SIGTERM` | Windows reports a closed console as SIGHUP |
| HTTPS trust | `NODE_OPTIONS=--use-system-ca` → Windows certificate store | Node 22.15+ |
| Launcher | `start-win-client.cmd` (LF-only, no labels or `goto`) | cmd.exe mis-parses labels in LF files |
| Entry guard | `pathToFileURL(argv[1]).href` | the Windows drive-letter bug of 2026-11-09 |

`launch.ts` changes the Neutralino config's `commandWindows` for the run and restores it in a `finally`, the same
way macOS does with `commandDarwin`; a run killed outright leaves the changed file (a `git diff` shows it).

## What was built and checked

335 vitest tests (contract vs. the JSON schema; checks against real http and https servers; core with fakes; the
built `ext/core.mjs` as a real process against a fake Neutralino WebSocket server; shell page with a fake Neutralino;
launcher with fake processes; config security properties), `tsc --strict`, the menu drift check, the decision-log
gate, and `npm run e2e:windows-shell`: the real shell page, real core process, real local server and real web app in
Chromium, Neutralino's client object faked — per app, plus `--server`. The e2e ran on Linux: it
proves the shared logic and the wiring, not the Windows-only parts.

## Not verified (needs a Windows machine)

1. A real Neutralino window from these files; `commandWindows` with the 8.3 short path, and the plain-`node` fallback.
2. Whether a console window flashes for the core despite `windowsHide`.
3. HTTPS to a real server through the Windows certificate store.
4. `taskkill /T` against a real uv interpreter; D161's orphan on a hard kill stays open.
5. `start-win-client.cmd` with arguments (`--server`, app name) in cmd.exe and in PowerShell.
6. WebView2: `<input type="file">` (D216), keyboard shortcuts, the frame without `sandbox`.
7. The 30 s server start timeout of the fourth real run (`e5-11-windows-client.md`): still unexplained. The server
   log `%LOCALAPPDATA%\Claudia\composes\state\server.log` is the first thing to read if it happens again.

## Findings about the macOS branch (not changed here)

* `.gitignore` there ignores `clients/macos/bin/`, which the new `bin/<app>.mjs` shims need; here the Windows `bin/`
  is deliberately tracked.
* CI there has no step running its e2e; here the `e2e` job builds the Windows client and runs `e2e:windows-shell`
  (macOS's `e2e:macos-shell` should run too once its client build is in that job).
* `ranges.md` there turned the free row into "D281–D290" and dropped the D300–D319 row (the latter only because it
  branched before main added it); expect a trivial conflict in `ranges.md`.

## Follow-ups

1. A first run on a real Windows machine (README, "Not verified"); expect small fixes.
2. Everything in `e5-11-macos-client-complete.md`'s follow-up list that is not OS-specific: `pick_file`, links and
   `print` from the frame, frame `sandbox`, designs for the status screens, self-signed certificates (D245).
3. A Job Object for D161 if orphaned servers show up in practice.
4. Installers, signing, Start Menu entry; lifting "no spaces in the path" once the app path is under our control.
5. `start-client.sh` and `start-mac-client.sh` still call `uv sync` without `--no-dev`.
