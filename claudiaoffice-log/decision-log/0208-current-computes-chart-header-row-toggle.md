---
id: D208
title: "A chart definition carries its own `header_row: bool` (default `True`), and the first row is only read as a header when it says so — the first column stays…"
status: current
applies-to: computes
date: 2026-11-09
round: "Charts: an explicit header-row toggle, after a reported bug (thirty-fifth round)"
supersedes: []
superseded-by: []
---

# D208 · A chart definition carries its own `header_row: bool` (default `True`), and the first row is only read as a header when it says so — the first column stays…

**A chart definition carries its own `header_row: bool` (default `True`), and the first row is only read as a header when it says so — the first column stays shape-only, as D207 already had it.** `ChartSpec.header_row`; `WorkbookModel.chart_figure` now computes `has_header_row = spec.header_row and last.row > first.row` instead of the row half of D207's "by shape alone" rule. `SheetChartInsertDialog.vue` gained a "First row is a header" checkbox (on by default, disabled — same as before this field existed — when the range has only one row). The insert dialog also widened from 440 to 520px (matching `RecoveryKeyDialog`/`StylesDialog`'s precedent for a form with this many fields), reported separately as too narrow to show its own content.

**Notes.** **Reported by the owner against D207 the same day it shipped:** a plain 2-column, 3-row range — column of categories, column of values, no header line of its own — silently lost its first row, because D207's shape-only rule had no way to tell "a range that happens to have room for a header" from "a range whose first row is actually one." Row 0 was read as a bogus header (its own data value became a fabricated series name), leaving only the second and third rows on the chart — exactly the owner's own description of the bug. Column 0 was not touched: a category column reading by shape alone is what the owner's own layout depended on and wanted kept. Only the row got an explicit toggle, not the column, because that is the one direction the bug actually showed up in; a symmetric column toggle can follow the same pattern later if it is ever needed.
