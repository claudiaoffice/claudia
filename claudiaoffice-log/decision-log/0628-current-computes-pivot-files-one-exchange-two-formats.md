---
id: D628
title: "Pivot tables in files: one format-neutral exchange, an adapter for ods and one for xlsx, a pivot is read only when the engine proves the file's cells"
status: current
applies-to: computes
date: 2026-11-16
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D628 · Pivot tables in files: one format-neutral exchange, an adapter for ods and one for xlsx, a pivot is read only when the engine proves the file's cells

**D625 is built. The rules for what a pivot is in a file are written once, in `pivot_exchange.py`; `ods_pivots.py` and `xlsx_pivots.py` only turn a `FilePivot` into XML and back.** A `FilePivot` is what every format says of a pivot: the cells it summarises (header row first), the cells it fills, row and column field, value fields, filters, the two totals, the words.

**Writing.** The cells a pivot fills are written as plain values (no file knows `PIVOT()`), and the pivot next to them: ods `table:data-pilot-table`, xlsx a cache (definition and records) and a `pivotTableDefinition` in Excel's tabular layout, `refreshOnLoad` on, so Excel and LibreOffice make the table again when they open it. A pivot that is no range with a header row (a query's result) is written as its values (`pivot-table:source`); one with no value field yet is not written (`empty`); an xlsx pivot with filters needs one free row for each above it and one more, because Excel puts the filter buttons there; without them it is written as values (`room`). A fresh export says nothing of a pivot it wrote.

**Reading: the rule of D370 applies.** A file's pivot is a live pivot of the model only when the engine, given the same source and the same fields, makes the very cells the file shows. The words of the file ("Total Result", "Sum - Amount", a German "Summe von") are read off those cells. The check ignores nothing but the field-name cells (`layout`). If the cells differ the pivot stays plain cells, and the loss `pivot-table:different` says so; a cell of a file is never changed by reading. What the model has no word for stays cells with its own detail: `external-source`, `data-model`, `calculated-field`, `grouping`, `slicer`, `pivot-chart`, `show-as`, `aggregation`, `hidden-items`, `top-n`, `sort`, `manual-sort`, `source`, `fields`. A source that is a range with no table of that name gets one made for it (`<pivot>_Source`), unless a table or name for the same range exists.

**A kept file** keeps its pivot parts byte for byte when nothing changed. When the source is edited the cells of the pivot are written as the new values (in xlsx the caches are also asked to be read again, `refreshOnLoad`); a change of the definition, a new or a deleted pivot is not written to a kept file and is counted as `pivot-table` by `ods_unwritten_changes` and `xlsx_unwritten_changes`, as a changed chart is. D625 said an edit inside a pivot's cells would be refused (`UnsupportedEdit`): nobody can type there, so there is nothing to refuse.

**The two total flags.** In ods `table:grand-total="row"` is the row of totals below and `"column"` the column at the right (checked against LibreOffice). In xlsx the flags follow Excel's own wording and its object model (`PivotTable.RowGrand`, "grand totals for rows"): `rowGrandTotals` is the column of totals at the right and `colGrandTotals` the row below. **Open:** LibreOffice, opening a file we wrote, shows the two the other way round (it writes neither itself), so the reading is from Microsoft's documentation and not checked in Excel. A file where the reading was wrong is not harmed on reading, since the engine must make the file's cells or the pivot stays cells; on writing, Excel makes the table again on opening and would show the totals the other way round. Say if a real Excel file shows otherwise, and one line in `xlsx_pivots._table` and `read_pivots` turns it.

**Not done.** `GETPIVOTDATA` (D481), pivot styles by purpose (D604), number formats of value fields, several row or column fields (D621). Whether Excel opens a written xlsx without a repair prompt can only be checked in Excel: the parts follow the schema order and LibreOffice and openpyxl read them.
