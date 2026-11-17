---
id: D625
title: "Pivot tables in xlsx and ods: ods first, the xlsx spike grows, a file is read as a pivot only when it gives the same cells"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D625 · Pivot tables in xlsx and ods: ods first, the xlsx spike grows, a file is read as a pivot only when it gives the same cells

**Built on 2026-11-16 (branch `pivot`); how, and what changed from this plan, is in D628.** What there was before: `xlsx.add_pivot_table` (D147), a spike that writes one row field and one summed value, not wired to the export; both importers only count a pivot as the loss `pivot-table`, and an edited file keeps the pivot parts as they were; `GETPIVOTDATA` is not done (D481).

1. **ods first** (D70): `table:data-pilot-table` with its source range, field orientations, functions and target range; LibreOffice computes it again on load, so the file can be checked with `scripts/odf_libreoffice_check.py` (D409).
2. **xlsx writing** grows from the spike: the cache definition and records, the pivot table definition with `rowItems` and `colItems` that match the grid (Excel repairs a file where they do not), data fields, the workbook relationships and content types; the cells of the grid are written into the sheet as values; `refreshOnLoad` as well. It joins the edit-and-reexport path (D371). *(Changed in D628: an edit inside a pivot's cells is not refused, since nobody can type there; the cells of a pivot whose source changed are written as the new values and the cache is asked to be read again.)*
3. **Reading** takes a pivot in only when its source is a sheet range or a table and everything it uses is supported, and only when what the engine computes equals the cells the file shows (the rule of D370: a cell is never wrong). Otherwise the cells stay values and the loss is said, with details (`external-source`, `data-model`, `calculated-field`, `grouping`, `slicer`, `pivot-chart`, `show-as`, `manual-sort`).
4. Pivot styles become styles by purpose, not Excel's table styles as direct formats (D604).
5. `GETPIVOTDATA` in both formats, once a pivot is in the model.
6. Test documents with pivots made by Excel and by LibreOffice, ideally the owner's real ones. Whether Excel opens a written file without a repair prompt can only be checked in Excel.
