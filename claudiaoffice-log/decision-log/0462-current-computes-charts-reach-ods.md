---
id: D462
title: "Bar charts go to and from ods as charts of their own; a chart tab becomes a sheet; a chart another program drew keeps its drawing"
status: current
applies-to: computes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D462 · Bar charts go to and from ods as charts of their own; a chart tab becomes a sheet; a chart another program drew keeps its drawing

**A bar chart of a workbook (a diagram floating on a sheet) is written to an ods as an embedded chart that reads the same
cells, pinned to its cell, and read back as the same diagram. What an ods cannot hold of a chart is a loss; a chart in a
kept file that Claudia did not draw is left as the file has it unless its definition changed.**

**Notes.**

* *Writing.* A chart is the folder `Object N` (`content.xml`, listed in the manifest with the chart media type) and a
  `draw:frame` with a `draw:object` in the `table:shapes` of its sheet, at the corner of its cell. The chart part has
  what LibreOffice writes for a bar chart: the cell ranges of its categories, series and series names, title, axis
  titles, legend, gridlines, the colours of `BAR_COLORS`, and a copy of its numbers (`local-table`) for a program that
  does not calculate. The frame's description is the chart's alt text (BITV 1.1.1).
* *Reading.* A chart is the model's own when it is a clustered, upright, two-dimensional bar chart over cells of one
  sheet of the file that is the chart `chart_figure` would draw for a range (first column categories, first row
  header, as many series as columns or rows). Anything else (another kind, stacked, horizontal, a series that is not
  the range's column, categories that are not the first column) stays in the file and is reported as `chart`.
  LibreOffice's own bar charts qualify; colours, fonts and the look of a foreign chart are not read.
* *Patching.* A kept file gets a chart added (a new `Object N`, frame and manifest entries), removed (frame, folder and
  entries), moved (the frame's corner, on another sheet too) and resized (the frame), described (`svg:desc`). A chart
  Claudia drew is drawn again for a changed definition, size or number. A chart another program drew is **kept as it is**
  when only its numbers, place, size or description changed (the frame and the sheet decide what it shows) and drawn the
  way Claudia draws a bar chart when its definition changed (`chart` / `look`). A chart of a removed sheet goes with it.
* *Chart tabs.* A file has no tab for a chart: a tab is written as a sheet of the tab's name (made unique) with the
  chart in it (`chart` / `tab`); it comes back as a sheet with a floating chart.
* *What is a loss.* `chart:source` (a chart that follows a name is written as the cells the name is now), `chart:rotation`
  (a chart in a file stands upright), `chart:empty` (a chart that reads nothing is not written), `chart:tab`.
* *Not here.* xlsx charts (see D463); other kinds of chart (the model has only bars).
