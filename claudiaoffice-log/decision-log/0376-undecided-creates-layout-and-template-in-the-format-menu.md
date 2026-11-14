---
id: D376
title: "Format ▸ Layout… (Ctrl+Alt+L) and Format ▸ Template… (Ctrl+Alt+E); a layout chip beside the style picker; the template line is the slide's description"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Real-world documents: templates and layouts in creates (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D376 · Format ▸ Layout… (Ctrl+Alt+L) and Format ▸ Template… (Ctrl+Alt+E); a layout chip beside the style picker; the template line is the slide's description

**Proposal.** Two Format menu entries after the style entries: **Layout…** (Ctrl+Alt+L) opens the layout picker,
**Template…** (Ctrl+Alt+E) the template editor. The bar gets a layout chip beside the style picker. Above the slide a
line names the template and the layout; it is the slide's accessible description. Footer and slide number keep full
contrast and carry a lock while editing; clicking them explains where they are defined instead of selecting them.

**Notes.** The keys follow the house pattern Ctrl+Alt+letter (D, F, O, R are taken). To check before building:
Ctrl+Alt+L locked the screen on older Ubuntu releases, and the macOS equivalents ⌘⌥L and ⌘⌥E. The generated menus of
the desktop clients need the two entries; every label goes through gettext (D31).
