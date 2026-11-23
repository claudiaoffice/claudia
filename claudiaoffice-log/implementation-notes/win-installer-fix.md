# Windows installer: the first real install (CODE-79, PROC-52, D746)

Branch `win-installer-fix`, written 2026-11-23. **Not run on Windows.** Run: the unit tests of `clients/neutralino`
(534, then the new ones), `tsc` typecheck, and the real launcher (compiled before and after the change) from a folder
laid out like an installation on Linux. The first CI run of `windows.yml` on this branch is the check on Windows.

## What the owner saw

An install "for my profile only": the server (service) installed and answered in a browser, and every icon (desktop
and Start menu) printed

    This app has not been built (missing index.html, shell\shell.js, ext\core.mjs in
    C:\Users\m\AppData\Local\Programs\clients\neutralino\apps\composes).

That folder does not exist; the apps are in `Programs\Claudia Office\client\apps\<app>`.

## Cause (CODE-79)

`run()` in `launch.ts` built the app folder from `defaultRepo()`. In an installation `findRepo` finds nothing and
`defaultRepo` returns the old "three levels up" guess: `client\dist` -> `Programs`. Reproduced on Linux with the
launcher compiled from `main` in a folder `Programs/Claudia Office/client/{dist,apps,bin,packaged.json}`: the same
message, with `Programs/clients/neutralino/apps/composes`. With the change the launcher finds the apps, makes the copy
under the person's folder, and goes on (in the Linux sandbox it then stops on a folder with a space in it, which is the
sandbox's, not the installation's).

## Why nothing caught it (PROC-52)

* Every launcher test passes `deps.appDir`; no test used the default.
* The CI step "A window opens, and starts the server it needs" is `continue-on-error: true` as a whole, because a runner
  may have no display for WebView2. A launcher that exits with an error looks the same as no display.

## Done

| Commit | What |
|---|---|
| CODE-79 | `appFolder` (`paths.ts`), used by `launch.ts` (`RunDeps.launcherFolder` to test it); tests `paths.test.ts`, `launch.test.ts` (red when `launch.ts` goes back to `defaultRepo`), `test_windows_packaging.py`; D746; the spec `specs/desktop/windows-installer.feature` (written with the fix, for the owner's review) |
| PROC-52 | `windows.yml`: a step of its own that needs no display and may not fail (*The launcher finds the installed app and prepares its window*); D747; `test_windows_packaging.py` |

## PROC-52 in detail

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
  reader the wrong way. It should say "reinstall Claudia" when `packaged.json` is there. Not part of CODE-79; offered as
  a follow-up.
* Nothing after the lookup (copy to `%LOCALAPPDATA%\Claudia\run`, Neutralino, core, WebView2) has run on Windows yet.

## Assumptions

* The decision numbers D746 and D747 are taken from the range D740-D759 (the Windows installer, branch `win-installer`,
  still open in `ranges.md`), not from a new reservation.
* The spec was written with the fix, not before it, because the bug was reported as broken behaviour with its cause one
  step away; it is for the owner to review. The scenario says a window opens; no automatic test checks that.
* "The app is prepared" in CI means: the copy of the app folder is there and the launcher did not print one of its own
  start-up errors. A runner without a display may still stop the window afterwards; that part stays advisory.
