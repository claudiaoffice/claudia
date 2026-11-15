---
id: D457
title: "Named ranges and tables go to ods and xlsx, are read back, and are patched into a kept file"
status: current
applies-to: computes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D457 · Named ranges and tables go to ods and xlsx, are read back, and are patched into a kept file

**A name of the model (D600) is written to every file the workbook is exported to: a range as a named range (ods) or a
defined name (xlsx), a table as a database range (ods) or a table part (xlsx). The ods import reads them, so a formula
that uses a name stays a formula, and a kept file has its names added, moved and taken out in place. What a file cannot
hold of a name is a loss, with a detail that says which.**

**Notes.**

* *Ranges.* ods: `table:named-range` with `table:base-cell-address` and `table:cell-range-address` (`$Data.$A$1:.$C$5`,
  the way LibreOffice writes it; read in every form the programs use), in the workbook's `table:named-expressions` after
  the sheets, or at the end of the sheet whose own it is. xlsx: `definedName` (`localSheetId` for the names of one
  sheet; it counts *all* the sheets of the workbook, chart sheets too).
* *Tables.* ods: `table:database-range` with `table:contains-header="true"`; one with a filter, without a header, or
  anonymous (`__Anonymous...`, which LibreOffice makes for an autofilter) is not a table and still counts as `filter`.
  xlsx: `xl/tables/tableN.xml` that the sheet points at with `tableParts`; no autofilter and no style are written.
* *The header of an xlsx table.* Excel keeps a table's column names equal to its header cells and repairs a file where
  they differ. A table is therefore written as a table only when every header cell is text and no two are alike; else it
  is written as the range it covers, with the loss `name` / `table-header`. A kept file whose header cell was edited
  gets the column renamed in its table part (before this, such a file was left for Excel to repair).
* *Formulas.* A name is written as it is. A column of a table (`Sales[Amount]`) is written to xlsx as it is, and to ods
  as the cell's value with the loss `formula` / `reference`: LibreOffice does not evaluate it in an `of:` formula (it
  shows `Err:508`; checked with LibreOffice 24.2), and the standard has no such reference.
* *What a file cannot hold* (loss `name`): `result` (a name a `SQL()` formula filled: the rectangle is the formula's
  spill, not a thing the file names), `purpose` (a table's colours by purpose and whether it grows by the row below:
  only Claudia knows them), `table-scope` (a table of one sheet: files have tables of the workbook, so it is written as
  a name of that sheet), `table-header` (xlsx only, see above).
* *What the file names that the model does not* (a constant or a formula as a name, a name of several areas, a table
  with a filter) stays in a kept file and is counted by the import, as before.
* *Patching.* A name that was taken out goes from the file; one that points somewhere else is written again where it
  stood (an ods name also when its sheet was renamed, since the file names the sheet by its text); a name that changed
  its form (range to table or back) goes and comes again in the other. A table of a kept xlsx that has more rows or
  columns is resized in its own part: its style, its calculated columns and the rest stay; columns are matched by place.
  A new table is a new part with the next free `id`, its relationship and its content type.
* *Not verified.* The sheet-scoped names of an ods are written as `table:named-expressions` at the end of the
  `table:table`; LibreOffice reads them there (checked), but the author has not found the place in the standard's
  schema that allows it. Excel itself was not available: the xlsx files were checked with openpyxl and LibreOffice.
