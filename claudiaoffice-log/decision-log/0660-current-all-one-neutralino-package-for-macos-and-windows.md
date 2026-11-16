---
id: D660
title: "One Neutralino package for macOS and Windows"
status: current
applies-to: all
date: 2026-11-15
round: "Code review follow-up: CODE-14, one package for the Neutralino clients"
supersedes: [D113]
superseded-by: []
---

# D660 · One Neutralino package for macOS and Windows

**A native client is one package per toolkit, not per operating system.** `clients/linux/` is the GTK client;
`clients/neutralino/` is the client for macOS and Windows, which replaces `clients/macos/` and `clients/windows/`. An
app is still an entry point, an identity, a menu manifest and its own desktop files, under `clients/<package>/apps/<app>/`.
The shell contract stays shared in `clients/contract/`. The Linux application id of composes stays
`de.claudiaoffice.composes`.

Inside `clients/neutralino/` everything is shared but `src/platform/`, which holds what differs by operating system: the
folders, the interpreter in the virtual environment, the Neutralino binary and how a window is started, the native
dialogs, the menu and its shortcuts, how a process tree ends. Two interfaces say what a platform gives: `HostPlatform`
(`platform/host.ts`, for the launcher and the core) and `PagePlatform` (`platform/page.ts`, for the shell page). Which
platform a piece of code is for is decided once (`platform/id.ts`): a bundle is built for one platform
(`npm run build:macos`, `npm run build:windows`; `npm run build` builds for the host) and behaves like it wherever it
runs; unbundled code, such as the launcher, asks Node. Both apps' `neutralino.config.json` name the core command for
both systems, so one app folder serves either.

A window ends the same way on both systems: its close button goes through the page, which quits the app. The
Windows shell used to let Neutralino close the window itself (`exitProcessOnClose: true`); it now follows macOS (D506).

**Notes.** The owner's answer of 2026-11-15 to `notes/code-review-2026-11-15.md`: "yes, share a package, and the name is
good!". Before, half of the sources (11 of 22 files, about 1,650 lines) and 10 test files were byte-identical copies,
and nothing checked that a fix reached both (CODE-14). The tests of what differs run for both platforms on any host
(`describe.each` over `MACOS_HOST` and `WINDOWS_HOST`), so a Linux CI job checks the Windows code as well. The start
scripts keep their names (`start-mac-client.sh`, `start-win-client.cmd`); their build switch is now
`CLAUDIA_SKIP_NEUTRALINO_BUILD`, and the old names still work. Closing through the page on Windows is checked by the
tests and the e2e script, not yet on a real Windows machine. The unused `apps/creates/inject/claudia-bridge.js` of
the old macOS package was not carried over (CODE-40).
