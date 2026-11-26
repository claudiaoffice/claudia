---
id: D1626
title: "An installed macOS app is a launcher script that prepares its window and becomes the Neutralino inside its own bundle"
status: current
applies-to: all
date: 2026-11-26
round: "E8.5 macOS installer, part 3: the package (branch `mac-installer`); designed 2026-11-25, built on Linux in CI by the owner's answers of 2026-11-26"
supersedes: []
superseded-by: []
---

# D1626 · An installed macOS app is a launcher script that prepares its window and becomes the Neutralino inside its own bundle

`claudia <app>.app/Contents/MacOS/claudia-<app>` is a shell script: it runs the launcher with the bundled node and
`--prepare`, which stages the app's folder into `~/Library/Caches/Claudia/run/<app>` and writes `window.sh` there (what
it changes in the environment, and `exec` of the Neutralino binary, quoted for any path), and then `exec`s that script.
So the process macOS launched becomes the window itself: **one Dock icon, the app's name and icon**, and quitting the
window ends the app. The Neutralino binary is `Contents/MacOS/neutralino` of the app, started as it is: nothing is
written into an installation. node's path has a space (`Application Support`) and a Mac has no short names, so the
core is started through a link `node` in the run folder. What the start prints is kept in `~/Library/Logs/Claudia/<app>.log`.

**Why.** The spike on the owner's Mac (2026-11-25, `spikes/e8-5-mac-launcher/`): with node as the launched process and
the window its child, the Dock shows two icons; with `exec`, one, named and drawn as the app.

**How.** `clients/neutralino/src/launch.ts` (`--prepare`, `windowScript`, `environmentChanges`, `shellQuote`),
`platform/macos.ts` (`runFolder`, `linkNodeIntoRun`, `windowBinary` of an installation), `packaging/macos/build.py`
(`app_program`). A checkout keeps the small `.app` bundle that `macos-app-bundle.ts` makes around the downloaded binary.
