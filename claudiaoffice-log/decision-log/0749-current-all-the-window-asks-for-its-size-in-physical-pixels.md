---
id: D749
title: "On Windows the shell page asks for the window's size again, in physical pixels, and centres the window"
status: current
applies-to: all
date: 2026-11-24
round: "The Windows installer, first real install (UX-76; branch `win-installer-fix`)"
supersedes: []
superseded-by: []
---

# D749 · The window's size is asked for again, in physical pixels

**The apps' configs keep saying 1280 × 860 (minimum 700 × 500) as CSS pixels. On Windows the shell page, once it runs,
multiplies that by the display scale (`devicePixelRatio`), takes at most nine tenths of the free screen
(`screen.availWidth`, `availHeight`), calls `window.setSize` and `window.center`, and only then goes on to the menu and the
core.** The arithmetic is `windowSizeFor` (`src/window-size.ts`); `WINDOW_WANTED` there is tested equal to the three configs.
`window.setSize` and `window.center` are on the three allow-lists. macOS is left alone (`sizesInPhysicalPixels: false` in
`platform/page.ts`).

**Why.** The owner's screen is 3840 × 1994 at 200%: the window opened 1280 × 860 *physical* pixels, which is 640 × 430 CSS
pixels, and showed a page that is too small for it. The framework's documentation does not say which unit it takes; the
owner's screenshot says physical, on Windows.

**Alternatives.** Computing the size in the launcher (it would have to ask Windows for the scale, in PowerShell or a C
helper) and passing `--window-width`: more moving parts, and the page knows the scale already. A fixed larger size: wrong
on every other scale. The cost of the chosen way: the window is created at the config's size and resized a moment later.

**Notes.** Not verified on Windows (assumption: Neutralino's sizes are physical pixels and the process is DPI-aware, as the
screenshot suggests). If a Neutralino release changed the unit, the nine-tenths cap would still keep a window mostly on the
screen only if the unit stayed physical; a second look at `window.getSize` after a release is the check.
