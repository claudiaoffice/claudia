---
id: D207
title: "A chart's range reads its first row and first column as headers whenever the range's own shape has room for them (`last.row > first.row`, `last.col >…"
status: current
applies-to: computes
date: 2026-11-09
round: "Computes charts: the diagram/chart RPC surface and the Plotly UI (thirty-fourth round)"
supersedes: []
superseded-by: []
---

# D207 · A chart's range reads its first row and first column as headers whenever the range's own shape has room for them (`last.row > first.row`, `last.col >…

**A chart's range reads its first row and first column as headers whenever the range's own shape has room for them (`last.row > first.row`, `last.col > first.col`) — by shape alone, never by sniffing cell contents — and a range too small on an axis falls back to generated labels ("Series 1", "1", "2"…) on that axis instead of refusing.** Deliberately **not** enforced as a new minimum-size rule in `claudia_computes.charts`'s own range validation (`_check_range`), which would have broken two already-merged tests that use a 1-wide out-of-bounds range to test bounds-checking specifically; instead handled entirely inside the new `WorkbookModel.chart_figure`. A text cell found inside the numeric data block plots as `0.0` rather than failing the whole chart.

**Notes.** There is no explicit "has headers" toggle in the draft yet (`ChartDraft` has none) — this convention is what a bare range means until one is added. The corner case worth stating plainly, caught while writing the tests: a 1-row, 2-column range still has its first *column* eaten as a header/category column (the column axis has room even though the row axis does not), leaving one series rather than two — correct and intentional under "by shape alone", not a bug, and the insert dialog's own preview line (`SheetChartInsertDialog.vue`) says so in plain words before a person submits a range too small to carry a header on a given side.
