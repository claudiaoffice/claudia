---
id: D1205
title: "Any rectangle of neighbouring cells can be merged, because Word needs it; the interface keeps it small"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1205 · Any rectangle of neighbouring cells can be merged, because Word needs it; the interface keeps it small

**Any rectangle of neighbouring cells of a table can be merged into one cell, and a merged cell can be split again.** Word files have them (`gridSpan`, `vMerge`) and odt files have them (`number-columns-spanned`, `number-rows-spanned`), so an imported table must keep them, and a person must be able to make one. A merge is `(first row, first column, rows, columns)`, by ids; the words are in its top-left cell and the cells it covers hold none.

**The interface does not make a feature of it.** Edit ▸ Merge Cells and Split Cell (menu and context menu only, shown while the caret is in a table), no option in the Insert dialog or in Table Options. A table with merges cannot be sorted by a column the merges cross (the command says why and refuses), and inserting a row or column inside a merge makes it grow; deleting one makes it shrink; moving a row or column across a merge is refused. A total ignores covered cells.

**Notes.** The first plan allowed only header groups. Confirmed 2026-11-18: "any set of neighbouring cells; I'm not a fan, but MS Word compatibility requires it. We should not make this a big option to the user in the UI." A merged cell that is not a rectangle cannot be written by either format, so only rectangles exist.
