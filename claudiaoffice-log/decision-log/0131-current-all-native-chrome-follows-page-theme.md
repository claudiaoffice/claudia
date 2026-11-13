---
id: D131
title: "Native shell chrome (the GTK/libadwaita About dialog) follows the page's own Dark Mode toggle, not the desktop's theme"
status: current
applies-to: all
date: 2026-11-06
round: "Menu redesign and accessibility baseline (nineteenth round)"
supersedes: []
superseded-by: []
---

# D131 · Native shell chrome (the GTK/libadwaita About dialog) follows the page's own Dark Mode toggle, not the desktop's theme

**Native shell chrome (the GTK/libadwaita About dialog) follows the page's own Dark Mode toggle, not the desktop's theme.** The window already reports `view.dark`'s resolved `checked` state to the shell on every change (click or system-triggered); the shell now also feeds that into `Adw.StyleManager.set_color_scheme()`, forced light or dark to match — never `PREFER_*`, since the in-app toggle is meant to override the desktop setting, not just suggest to it.

**Notes.** Owner's report: the About dialog stayed whatever colour GTK's own theme was, regardless of the document's own Dark Mode setting. Chosen (over leaving native chrome theme-independent) via `AskUserQuestion`. No new shell-contract message needed — `set_action_states` already received everything required.
