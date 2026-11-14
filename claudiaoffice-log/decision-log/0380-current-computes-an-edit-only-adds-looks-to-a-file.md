---
id: D380
title: "Writing a changed look into an edited xlsx or ods only adds to the file's styles; the file's own named style of the same name is the parent"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: cell formats and number formats (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D380 · An edit only adds looks to a file; the file's own named style of the same name is the parent

**When an imported xlsx or ods file is written back after an edit (D371, D413), a cell, row or column whose look
changed gets a new look of its own, and nothing the file had is changed or renumbered.** A look changes when the
cell's styles change, or when a style it has is changed itself (its CSS, its number format, or its name, which
decides the named style it is written as). Cells, rows and columns whose look did not change keep exactly what the
file gave them, whatever claudia made of it on import.

* **xlsx:** the new look is an entry appended to `cellXfs`, with its font, fill and border appended to their lists
  (once, however many cells take it) and its number format Excel's own number where Excel has one, the file's
  `numFmt` with that code where the file has one, or a new one from 164 up. A row gets `s` and `customFormat`; a
  `col` element that reaches beyond a restyled column is cut, so its other columns keep their width and look.
* **ods:** the new look is an automatic style of its own (`claudia-ce1`...) in `content.xml`, number styles
  likewise; a repeated row or column is cut where a restyled run begins or ends, and gets the style as its default
  cell style.

**The named style a new look is based on is the file's style of the same name** (*Normal* or *Default* for Body
text). A named style the file does not have yet is added (`cellStyleXfs` and `cellStyles`; `office:styles`). The new
look carries the whole look of the cell, so it shows the same even where the file's named style of that name looks
different from claudia's.

**Notes.** Patch 3c of the real-world documents round. The alternative — rewriting `styles.xml` from the model —
would have changed the look of every cell whose file look claudia does not fully hold (a pattern fill, a rotation,
a conditional format pointing at a `dxf`), which D371 and D413 rule out. A style taken away from a cell writes the
default look (`s` 0, `Default`), not "nothing", so that a row or column style beneath does not show through where the
person did not ask for it.
