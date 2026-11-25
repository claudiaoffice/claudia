---
id: D1603
title: "Menu titles never change; a menu or context menu with nothing left says why"
status: current
applies-to: all
date: 2026-11-25
round: "Menus that show what fits (menu work, branch `menus`, grilling of 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1603 · Menu titles never change; a menu or context menu with nothing left says why

**The top-level menus (File, Edit, Insert, Format, View, Tools, Preferences, Help) never appear, disappear or move; everything below them may. Separators at the start, at the end or doubled collapse, and a submenu with nothing left disappears. A menu with nothing left shows one greyed line saying why** ("Nothing to insert: you can only look at this document"). **A right press where no entry fits opens a context menu with one greyed line saying why**, so the press does not look broken; Shift + right press still gives the browser's own menu. **An open menu stays as it was when it opened**; whether an entry fits is checked again when it is chosen, with the notice of D1604 if it no longer does, and changes show the next time a menu opens.

**Notes.** A stable menu bar keeps people's bearings, keyboard and screen-reader users' most of all. Hiding never changes the order of the entries that remain, which is what consistent navigation asks for (WCAG 3.2.3, BITV); the trial includes a screen-reader pass before the switch is decided (D1600).
