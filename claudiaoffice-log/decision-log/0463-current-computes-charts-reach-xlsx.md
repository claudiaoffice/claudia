---
id: D463
title: "Bar charts go to and from xlsx as charts of their own; the plan of a chart is the same as for ods"
status: current
applies-to: computes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D463 · Bar charts go to and from xlsx as charts of their own; the plan of a chart is the same as for ods

**D462 holds for xlsx as it does for ods: a bar chart of a workbook is written as a chart that reads the same cells,
pinned to its cell, read back as the same diagram, and patched into a kept file without touching a chart nobody
changed. What differs is only what the file format has.**

**Notes.**

* *Writing.* A chart is `xl/charts/chartN.xml` (`c:barChart`: a series for each column or row with its name, categories
  and values as references and a cache of the numbers, title, axis titles, legend, gridlines, the colours of
  `BAR_COLORS`), reached from the drawing of its sheet (`xl/drawings/drawingN.xml`, a `oneCellAnchor` at the cell with
  the size, a `graphicFrame` whose `descr` is the alt text, BITV 1.1.1). The sheet gets its `<drawing>` where the
  standard has it (before `legacyDrawing` and `tableParts`); content types and relationships follow.
* *Reading.* The same rule as for ods: a chart is the model's own when its plan equals the one `chart_figure` would draw
  for the cells it reads (shared in `chart_plan.py`). Excel has no attribute for the direction of the series; it is
  deduced from the cells. A frame pinned by two cells has the size its `xfrm` states (LibreOffice does), else the size
  of the cells it reaches by the widths and heights of the file (Excel states none).
* *Patching.* As for ods (D462): add, remove, move, resize, describe, redraw; a drawing the sheet has gets the new
  anchor with an id of its own, one it has not is made. A chart is "ours" when its part equals what we would draw for the
  baseline, so a chart Excel or LibreOffice drew keeps its drawing (`chart` / `look` when its definition changed).
* *Losses.* The same four as for ods: `chart:tab`, `chart:source`, `chart:rotation`, `chart:empty`.
* *Not here.* Other kinds of chart (the model has only bars); the look of a foreign chart.
