---
id: D749
title: "On Windows the launcher has Neutralino size the window in logical pixels, so the window grows with the display scale"
status: current
applies-to: all
date: 2026-11-24
round: "The Windows installer, first real install (UX-77; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D749 · The launcher has Neutralino take the window's size in logical pixels

**The apps' configs keep saying 1280 × 860 (minimum 700 × 500). On Windows the launcher writes `modes.window.useLogicalPixels:
true` into the copy of the app's config it starts the window from (`setLogicalPixels`, `src/core-command.ts`, called by
`run()` in `src/launch.ts` where `HostPlatform.windowSizeInPhysicalPixels` is true) and takes it out again afterwards, as it
does for the core's command and the inspector.** Neutralino then multiplies the width and the height by the display scale
when it creates the window: 1280 × 860 at 200% is 2560 × 1720 physical pixels. macOS is not touched (its window sizes are in
points already, and what the option does there is not known).

**Why.** The owner's screen is 3840 × 1994 at 200%: the window opened 1280 × 860 *physical* pixels, which is 640 × 430 CSS
pixels, and showed a page that is too small for it (screenshot, 2026-11-24).

**What came before, and why it is gone.** The first version had the shell page ask for the size again with
`window.setSize`, scaled by `devicePixelRatio`, and then `window.center`. On the owner's machine the window never
answered, and with the call awaited every app stayed on "Starting…" (CODE-85). The call not awaited left the window at the
config's size: the request has no effect there. The code, its two allow-list entries and its tests are removed; the
Neutralino issues about `setSize` on scaled Windows displays (#648, #823) say it is unreliable.

**Alternatives.** Starting the window maximised (`modes.window.maximize`): fills any screen, but nobody asked for it, and a
document window that is always maximised is another look. Computing the size in the launcher from the Windows scale (a C or
PowerShell helper): more parts, and the option does the same. Cost of the chosen way: the minimum size stays in physical
pixels (the option scales width and height only: Neutralino issue #1637), and the window is not capped to the free screen: at
125% or 150% on a 1080p screen 1280 × 860 logical pixels is taller than the free screen, and the window must be moved or
maximised by hand.

**Notes.** Not verified on Windows: the owner's next install is the check. If the option is not honoured for the window as it
is created, nothing changes and the size stays the config's. A cap and a centre need a window that answers, or the launcher
knowing the screen; both are left out until this is seen to work.
