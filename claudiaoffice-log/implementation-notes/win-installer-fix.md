# Windows installer: the first real install (CODE-93, PROC-57, D746)

Branch `win-installer-fix`, written 2026-11-23. **Not run on Windows.** Run: the unit tests of `clients/neutralino`
(534, then the new ones), `tsc` typecheck, and the real launcher (compiled before and after the change) from a folder
laid out like an installation on Linux. The first CI run of `windows.yml` on this branch is the check on Windows.

## What the owner saw

An install "for my profile only": the server (service) installed and answered in a browser, and every icon (desktop
and Start menu) printed

    This app has not been built (missing index.html, shell\shell.js, ext\core.mjs in
    C:\Users\m\AppData\Local\Programs\clients\neutralino\apps\composes).

That folder does not exist; the apps are in `Programs\Claudia Office\client\apps\<app>`.

## Cause (CODE-93)

`run()` in `launch.ts` built the app folder from `defaultRepo()`. In an installation `findRepo` finds nothing and
`defaultRepo` returns the old "three levels up" guess: `client\dist` -> `Programs`. Reproduced on Linux with the
launcher compiled from `main` in a folder `Programs/Claudia Office/client/{dist,apps,bin,packaged.json}`: the same
message, with `Programs/clients/neutralino/apps/composes`. With the change the launcher finds the apps, makes the copy
under the person's folder, and goes on (in the Linux sandbox it then stops on a folder with a space in it, which is the
sandbox's, not the installation's).

## Why nothing caught it (PROC-57)

* Every launcher test passes `deps.appDir`; no test used the default.
* The CI step "A window opens, and starts the server it needs" is `continue-on-error: true` as a whole, because a runner
  may have no display for WebView2. A launcher that exits with an error looks the same as no display.

## Done

| Commit | What |
|---|---|
| CODE-93 | `appFolder` (`paths.ts`), used by `launch.ts` (`RunDeps.launcherFolder` to test it); tests `paths.test.ts`, `launch.test.ts` (red when `launch.ts` goes back to `defaultRepo`), `test_windows_packaging.py`; D746; the spec `specs/desktop/windows-installer.feature` (written with the fix, for the owner's review) |
| PROC-57 | `windows.yml`: a step of its own that needs no display and may not fail (*The launcher finds the installed app and prepares its window*); D747; `test_windows_packaging.py` |
| CODE-94 | `startPageAction` (`web/app/lib/open.ts`) knows `help.about`; `OpenDialog.vue` mounts `AboutDialog`; `web/tests/open.test.ts`; D748; `specs/desktop/about.feature` |
| UX-81 | `setLogicalPixels` (`core-command.ts`), `HostPlatform.windowSizeInPhysicalPixels`, called by `run()` in `launch.ts`; the first attempt (`window-size.ts`, `ShellPage.fitWindow`, `window.setSize` and `window.center` on the allow-lists) is removed; tests `launch.test.ts`, `core-command.test.ts`, `build-shell.test.ts`; D749; `specs/desktop/window-size.feature` |
| UX-83 | `SUITE_ICON` and `claudia.ico` in `build.py`, `claudia.iss` (`SetupIconFile`, `UninstallDisplayIcon`), `clients/neutralino/suite-icon.svg` and `.png`, a check in `windows.yml`; tests `test_windows_packaging.py`; D751 |
| UX-82 | `packaging/windows/launcher/claudia-start.c`, `build.py launcher` and `stage --launcher`, `claudia.iss` (shortcuts and post-install start), `windows.yml` (build, try, stage); tests `test_windows_packaging.py`; D750; `specs/desktop/windows-launcher.feature` |

## PROC-57 in detail

The new step starts the installed launcher and waits for the copy of the app in `%LOCALAPPDATA%\Claudia\run\composes` and for
the core's command in its configuration (written just before the window starts). If the launcher ends first, the step
fails with its error output, unless the copy is whole and the launcher said nothing, or only "Could not start" (a runner
without a display). It stops the launcher, the window, the server and the core's node, which holds the copy. The step "A
window opens..." stays `continue-on-error`. **Not run:** the YAML and the PowerShell have not run on a Windows runner (actionlint
passes); the PowerShell is of the kind the other steps use. A window that dies after it started is not seen by this step,
and the config is read while the launcher is alive, so a very fast failure could be missed by the poll and then reads as
"ended, copy whole, no error text": not a failure.

## Not done, on purpose

* The install test installs for all people in `C:\Program Files`; the owner's install was for the profile only. The code that
  failed does not depend on it, so not added; a profile-only run of the same steps is a follow-up if wanted.

* The message of `missingFiles` still says "Run 'npm ci && npm run build'" for an installed client, which sent the first
  reader the wrong way. It should say "reinstall Claudia" when `packaged.json` is there. Not part of CODE-93; offered as
  a follow-up.
* Nothing after the lookup (copy to `%LOCALAPPDATA%\Claudia\run`, Neutralino, core, WebView2) has run on Windows yet.

## Assumptions

* The decision numbers D746 and D747 are taken from the range D740-D759 (the Windows installer, branch `win-installer`,
  still open in `ranges.md`), not from a new reservation.
* The spec was written with the fix, not before it, because the bug was reported as broken behaviour with its cause one
  step away; it is for the owner to review. The scenario says a window opens; no automatic test checks that.
* "The app is prepared" in CI means: the copy of the app folder is there and the launcher did not print one of its own
  start-up errors. A runner without a display may still stop the window afterwards; that part stays advisory.

## UX-81 and UX-82: what is assumed and what has not run

* **Neutralino's window sizes are physical pixels on Windows** (the owner's screenshot: 1280 × 860 became about 640 × 430 CSS
  pixels at 200%). `modes.window.useLogicalPixels` is documented as the switch that scales width and height by the display
  scale; **it has not been run**, and it is not known whether Neutralino 6.8 honours it for the window as it is created. If it does
  not, the window stays as small as it was. It is set on Windows only; what it does on macOS is unknown. Not scaled by it: the
  minimum size. Not capped to the free screen: on a small screen at 125% or 150% the window can be taller than the screen.
  The first attempt (`window.setSize` from the page) never took effect on the owner's machine and is removed.
* The nine tenths of the free screen of the first attempt are gone with it. A cap and a centred window are open.
* The icon of the setup file and of the Programs entry (UX-83) is made from a committed PNG; not seen on Windows.
* **`claudia-start.exe` was compiled here** (Zig's `cc`, target `x86_64-windows-gnu`, `-municode`, GUI subsystem, no warnings)
  **and never run**: there is no Windows or Wine in this workspace. CI uses MinGW `gcc`, installed with `choco` where the
  runner has none; the flags `-mwindows -municode` are the usual ones and were not tried with that compiler.
* The program shows a message box for every exit code other than 0. If Neutralino exits with a non-zero code when its window is
  closed, every close will show one; the first real run will tell.
* **Not understood:** why the console stayed open after the app was closed. If a `node.exe` remains in the task manager after
  closing an app, the cause is in the Node launcher or the core (not in this change), and it is now invisible.
* The log of the start is `launcher.log`, the run before `launcher.log.old`; only the last two starts are kept.
* Neutralino's two start-up errors (`resources.neu` missing, `/favicon.ico`) are now in the log, not fixed: offered as
  a follow-up (size 3).
* The Windows 11 look of the native menu is not in this branch: see the answer to the owner.
* The message boxes of `claudia-start.exe` are English only (coding standard 11 asks for translation): offered to the owner as
  a decision (D750, known limits). The C program has no linter or formatter in CI either (standard 1): `-Wall -Wextra` was
  clean with Zig's cc, nothing more. `choco install mingw` (only where the runner has no `gcc`) is unpinned (standard 7).
* The code review found, and this change fixed: argument quoting that swallowed the closing quote of an argument ending in a
  backslash (now in the CI step), unchecked `swprintf` results, and the arguments being checked after the old log was moved.
* **CODE-95:** the first version of the resize was awaited before the core was started, and the window never answered on the
  owner's machine: all apps stayed on "Starting…". It is now not awaited. Why the window does not answer is not known, so it
  is not known that the window is resized at all; the page's console (`claudia-start.exe <app> --debug`) says.

## CODE-96 and CODE-97: what is assumed and what has not run

* **CODE-96 (Neutralino's start-up errors):** the cause was **read** from Neutralino's documentation, not measured: the app is
  started with `--res-mode=directory` (D752, since v6.3) so it reads `resources/` from the app folder instead of a missing
  `resources.neu`, and the shell page names its icon (`<link rel="icon">`), so the browser does not ask for `/favicon.ico`.
  Whether both lines are gone from `launcher.log` on a real install has not been seen.
* **CODE-97 (a node.exe after a killed window):** **measured** in CI on a real window (windows-2022): a killed Neutralino
  leaves the core running, a closed one does not. The first fix (watch the core's parent) failed there: the core's parent is
  a shell, not Neutralino. The fix now is the pid of the window (`NL_PID`) which the page sends with `start` (D753). Why the
  link to Neutralino stays up after the kill is still not known. The CI step *The core of a window ends when its window is
  closed or killed* is the proof; its last result is in the pull request.
* An older page that does not send `windowPid` is not watched by pid (parent watch and link only).
* A window killed in the first second or two, before its page has sent `start`, still leaves its core (seen once in CI): the core does not know the pid yet. Offered: end a core that gets no `start` within a minute or two.
