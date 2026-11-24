---
id: D751
title: "The setup file and the entry in Programs show the icon of the whole suite, not the icon of one app"
status: current
applies-to: all
date: 2026-11-24
round: "The Windows installer, first real install (UX-79; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D751 · The installer's icons are the suite's

**`SetupIconFile` (the installer's file) and `UninstallDisplayIcon` (the entry in "Apps & features") are
`icons\claudia.ico`: the three-dot icon of the suite (ink tile, three dots in rose, teal and apricot: `notes/design-system.md`,
"Suite favicon").** The shortcuts of the apps keep the icon of their app. The drawing is `clients/neutralino/suite-icon.svg`,
equal to `web/public/favicon.svg` (a test says so); `suite-icon.png` (256 × 256, made from it with `rsvg-convert`) is what
`build.py stage` turns into `claudia.ico`, as it does for the apps.

**Why.** Both used `composes.ico`, so the suite looked like its word processor (the owner, 2026-11-24).

**Alternatives.** Rendering the PNG in the build: needs a rasteriser on the Windows runner; a committed PNG is how the apps do it.
**Notes.** Not run on Windows: the icon of the installer file and the Programs entry are the owner's check. The icon of
the Windows client's own window and taskbar comes from each app's config and stays the app's.
