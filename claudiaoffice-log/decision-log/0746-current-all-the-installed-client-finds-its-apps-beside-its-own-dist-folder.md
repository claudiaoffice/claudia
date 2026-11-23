---
id: D746
title: "The launcher finds its apps beside its own folder, in a checkout and in an installation alike"
status: current
applies-to: all
date: 2026-11-23
round: "The Windows installer, first real install (CODE-79; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D746 · The launcher finds its apps beside its own folder, in a checkout and in an installation alike

**The app folder is `apps/<app>` beside the folder the launcher runs from** (`dist/`, or `src/` in the tests): from
`<client>/dist/launch.js` it is `<client>/apps/<app>`. `appFolder` in `clients/neutralino/src/paths.ts` says so. The
launcher no longer asks for the repository (`defaultRepo`) to find it.

**Why.** D741 made the installed client "the checkout's client plus a marker": the installer lays `client/` out as
`clients/neutralino` is laid out. The launcher still looked for its apps at `<repository>/clients/neutralino/apps/<app>`,
and an installation has no repository: `defaultRepo` fell back to "three levels up" and named
`%LOCALAPPDATA%\Programs\clients\neutralino\apps\composes`, which does not exist. The marker (`packaged.json`) is read
from the app folder, so it was never reached, and the person was told to run `npm ci && npm run build`. No icon of the
first real install opened a window.

**Rule to keep.** What a launcher needs next to itself (apps, marker) is found relative to itself. The repository is
only for a checkout's frontend build and Python (`findFrontend`, `findServerPython`), which an installation gets from
its marker (D741). `packaging/windows/build.py` and `appFolder` are two halves of one layout; the test
`test_the_launcher_finds_the_apps_where_the_stage_and_the_checkout_have_them` holds them together.

**Notes.** `defaultRepo` stays for those two lookups. The message of `missingFiles` still speaks of building the client;
for an installed client it should say "reinstall" (not done here, see the implementation note).
