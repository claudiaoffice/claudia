---
id: D1320
title: "Get, on the banner of a missing font, goes to Server settings ▸ Fonts"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1320 · Get, on the banner of a missing font, goes to Server settings ▸ Fonts

**Decided 2026-11-19** while building D1306, which said "Get" is for administrators only and left open what it does.

The server has no way to fetch a font by its name: *Server settings ▸ Fonts* adds fonts from files an administrator provides (`AddFontsDialog`). So **Get opens Server settings ▸ Fonts** (`/admin/#fonts`) in a new tab, where the administrator adds the font; the banner names the missing families. It is drawn only where this browser tab is signed in to the server's settings; everybody else sees "Ask an administrator to add it." The server refuses anybody else whatever the page shows (D251), and the report (`font_report`) never blocks opening.

If the owner wants "fetch by name" (a catalogue of fonts the server may download), that is a feature of its own: it needs a source list and licence handling (E3.13).
