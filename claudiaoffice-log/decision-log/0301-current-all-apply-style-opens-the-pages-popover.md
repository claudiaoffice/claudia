---
id: D301
title: "In a native shell, Apply style… opens the page's own popover; nothing new in the shell contract"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D301 · In a native shell, Apply style… opens the page's own popover; nothing new in the shell contract

**In a native shell (GTK, and Neutralino on Windows and macOS) "Apply style…" is a plain page action that opens the web page's own popover with the styles drawn in their looks.** The shell's manifest has one entry `format.apply-style` with no per-style items and no native widgets; nothing is added to the shell contract (JSON schema v1), so its version does not change (additive changes keep it). The web menu bar, which is the page's own, shows the same list as a flyout.

**Notes.** The alternative was a native submenu in each shell with a custom widget per entry. GTK menus cannot draw an entry in a font and a colour without custom widgets and a new contract message, and Windows and macOS menus cannot at all; all of that would only make the three shells look different from each other. The popover is the one place that can draw a style in its look in all three, and `StyleMenu.vue` already has it. Same pattern as "All Styles…" today (`format.all-styles` is a page action). The owner confirmed it for Windows and macOS; for GTK it was proposed in the same words and has not been confirmed separately, so a shell author who finds a GTK reason against it should ask before building a native flyout.
