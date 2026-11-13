---
id: D297
title: "Following a computation lights the connected cells of the window and dims the rest — no arrows"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D297 · Following a computation lights the connected cells of the window and dims the rest — no arrows

**Clicking a cell that takes part in a computation lights up every connected cell inside the viewport — inputs, calculations and outputs, each in its own role — and dims all other cells while the display lasts.** The owner approved the screens except for arrows: **there are no arrows between cells, only lit cells.** A role is never shown by colour alone (BITV): each also has a shape mark and a bar on the cell's left edge.

`trace(sheet, row, col, reach, window)` computes the roles over the whole connected set and cuts the list to the window; `reach` is `group` (everything connected) or `chain` (only what the cell feeds and what feeds it). Cells on other sheets are counted per sheet so the tab can say "3 connected". At most 20 000 cells are followed; `truncated` says when that was not enough. It is a view, not an edit: nothing is logged.

**Notes.** The web and GTK clients are designed (mocks 3a/3b) but not built in this branch: see the implementation notes.
