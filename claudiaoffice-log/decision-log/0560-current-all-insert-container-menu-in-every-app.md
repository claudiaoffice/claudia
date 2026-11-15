---
id: D560
title: "Insert ▸ Container ▸ LaTeX, Mermaid, Typst is in every app, as a menu of its own"
status: current
applies-to: all
date: 2026-11-15
round: "Rendered text containers: the screens (branch containers)"
supersedes: []
superseded-by: []
---

# D560 · Insert ▸ Container ▸ LaTeX, Mermaid, Typst is in every app, as a menu of its own

**Every app has an Insert menu between Edit and Format, and its Container submenu offers LaTeX, Mermaid and Typst, with the keys Ctrl+Alt+Shift+F, G and Y.** The menu bar is now eight menus in every client (File, Edit, Insert, Format, View, Tools, Config, Help); this extends D120. The entries are built once (`insertMenu` in `lib/document-menus.ts`) and listed once in the shell manifest, so the web, Gtk, macOS and Windows menus cannot drift (D361). An entry is off for a viewer and while the server cannot make that kind (its tool is not set up).

**Notes.** The keys avoid Ctrl+Alt+L/M/T and digits, which desktops and AltGr layouts use. Composes already had an Edit ▸ Insert submenu for the two hyphens; it stays, and moving it under the new menu is a follow-up. The front page has no Insert menu.
