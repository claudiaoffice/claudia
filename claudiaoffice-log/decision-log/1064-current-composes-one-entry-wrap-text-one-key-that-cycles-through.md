---
id: D1064
title: "One entry, Wrap Text, one key that cycles through the four modes"
status: current
applies-to: composes
date: 2026-11-17
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1064 · One entry, Wrap Text, one key that cycles through the four modes

**Format ▸ Wrap Text has one key, `format.wrap-text` (Ctrl+Alt+L, free in the three manifests), and each press moves the selected object to the next mode: over, around, above and below, behind, and back to over.** The owner chose one cycling key over four entries on 2026-11-17.

**Notes.** One entry, one key in the web app and the GTK client (menu-parity rule). The current mode is shown in the menu entry and announced to screen readers. A press is one `set_wrap` command, so the history says what happened and undo steps back one mode. The distance is not on the key; where it is set is open.
