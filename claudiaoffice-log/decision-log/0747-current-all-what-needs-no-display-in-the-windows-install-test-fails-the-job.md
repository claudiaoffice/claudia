---
id: D747
title: "In the Windows install test, what needs no display is a step of its own and fails the job"
status: current
applies-to: all
date: 2026-11-23
round: "The Windows installer, first real install (PROC-53; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D747 · In the Windows install test, what needs no display is a step of its own and fails the job

**The step that starts the installed launcher is split in two.** `windows.yml`, job `test`:

1. *The launcher finds the installed app and prepares its window* starts `node.exe client\bin\composes.mjs` from the
   installation and waits (60 s) until the copy of the app in the person's own folder is there
   (`%LOCALAPPDATA%\Claudia\run\composes`: `index.html`, `ext\core.mjs`, D741) and the core's command is written into
   its configuration, which the launcher does just before it starts the window. A launcher that ends first fails the job,
   with its error output in the log, unless the copy is whole and the launcher had no error of its own to say (or only
   "Could not start", a window that would not open): that is for the next step. It needs no display and **is not allowed
   to fail**; it also stops the nodes of the installation that a window leaves behind.
2. *A window opens, and starts the server it needs* stays as it was, including `continue-on-error: true`: whether a runner can
   show a WebView2 window is not known (D742).

**Why.** The step had been one, advisory as a whole, because of its last part. A launcher that stopped on its own error
(CODE-83: it could not find the installed apps) looked the same as a runner without a display, and the first real install
had a green CI and no working icon. Everything the launcher does before it starts the window needs no display; only that
may be strict. The test `test_a_launcher_that_cannot_prepare_its_window_fails_the_install_test` keeps the step from being
made advisory again.

**Notes.** Not run on Windows (the first run of `windows.yml` on `win-installer-fix` is the check). The install the job tests
is for all people (`/ALLUSERS`, `C:\Program Files`); the owner's failure was an install for the profile only. The launcher
code that failed does not depend on the folder; a test of the profile-only install as well is a possible follow-up.
