---
id: D307
title: "A computes cell has a Box slot and a Paragraph slot; style ranges per sheet, allow-list version 3"
status: current
applies-to: computes
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D307 · A computes cell has a Box slot and a Paragraph slot; style ranges per sheet, allow-list version 3

**A cell is styled through the same two slots as everything else (D304):** a Box style (background, borders, padding, vertical alignment) and a Paragraph style (alignment, line height, text properties). The decision of E6.13 that cell styles use CSS table properties is kept, and settles its open points:

* The allow-list goes to `CSS_VERSION` 3 with `vertical-align` and `white-space` (wrapping), the two properties a cell needs that no style had.
* A sheet stores **style ranges in layers** (sheet default, column, row, range, cell, in that order), not a style per cell; a new command `SetCellStyle` respects locks and undo, and ranges move with row and column edits (the lesson of D135).
* The grid draws styled empty cells without an element per cell.
* **Number formats stay separate from styles** (D75); row height and column width stay layout (D135).

**Notes.** Answers the owner's question what it takes for a cell to use composes' Paragraph class: nothing special in the cell, but the style model of D303–D305 first, because otherwise computes would get a second way of saying what a paragraph looks like. Cell styles are the last phase of the round, after the core facet table and the menu and dialog work.

*Refined on 2026-11-11 by D317: the layer order is the lookup order; what a person sees after an action is decided by the last action.*
