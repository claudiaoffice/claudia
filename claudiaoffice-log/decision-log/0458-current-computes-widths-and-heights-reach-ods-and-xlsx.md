---
id: D458
title: "Column widths and row heights go to ods and xlsx, are read back, and are patched into a kept file"
status: current
applies-to: computes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D458 · Column widths and row heights go to ods and xlsx, are read back, and are patched into a kept file

**The size of a column or row that a person set (D135) is written to every file the workbook is exported to, read by the
imports, and added, changed or given up in place in a kept file. `layout` is no longer a loss of either format; the one
loss that remains is a size Excel cannot hold.**

**Notes.**

* *Units.* The model counts pixels. xlsx counts a column in characters (7 pixels each: Calibri 11, Excel's own measure)
  and a row in points (0.75 pixel each). ods counts both as lengths (`2.258cm`, `0.5in`, `12pt`...; a pixel is 1/96 inch).
  Everything is rounded to whole pixels on the way in and kept within the sizes the model allows
  (`MIN_/MAX_COL_WIDTH`, `MIN_/MAX_ROW_HEIGHT`).
* *Which sizes come in.* Only a size somebody set: xlsx `col` with `customWidth` and `row` with `customHeight`; ods a
  `table-column` style that is not `use-optimal-column-width` and a `table-row` style that is not
  `use-optimal-row-height`. A size equal to the model's default is not stored (it is no size). Only the first 256
  columns and 10,000 rows are read: a file gives *every* column a width (LibreOffice writes one for a thousand columns
  past the last used), and nobody sees a width out there. Both caps are silent; a patch never touches a size it did
  not change, so the file keeps them.
* *The file's own default.* A line the file does not size comes in at the model's default (96 × 26 pixels), not at the
  file's (Excel: 64 × 20; LibreOffice: 2.258cm columns and sizes every column anyway). The model has no default per
  sheet. A fresh xlsx now says what the model shows (`sheetFormatPr`: `defaultColWidth`, `defaultRowHeight`,
  `customHeight`), so rows that were 20 pixels in Excel before are 26, as in Claudia.
* *What a given-up size becomes.* A size that was set and is no more is written as the model's default, explicitly: the
  file's own default may be another, and `customWidth` is how the next import tells a size from a left-over.
* *Excel's limits.* 255 characters and 409.5 points. A size beyond is written at the limit and reported as `layout` /
  `beyond-excel-limits` (also by the patch, through `xlsx_unwritten_changes`). ods has no limit.
* *Writing.* xlsx: the `col` elements are the runs of columns with a look cut where a width starts or ends and joined
  where neighbours are alike (`xlsx_layout.column_runs`); every `col` says its width (openpyxl's own 13 characters
  would come back as a width of 91 pixels). ods: `table-column` and `table-row` automatic styles (`co1`, `ro1`...;
  `claudia-co1` in a patch) shared by sizes, with `style:use-optimal-row-height="false"`.
* *Patching.* xlsx: a `col` that reaches over a changed column is cut so the others keep width and look
  (`SheetPatch.resize_columns`), a row gets `ht` and `customHeight` (`resize_rows`); a sheet whose sizes changed counts
  as changed. ods: the same splitting of repeated `table-column` / `table-row` elements as for default cell styles
  (`_restyle_columns`, `_patch_rows`, `_append_rows`), columns and rows beyond the last one of the file are declared.
  A resized ods line gets a new automatic style of its own, so what its old style held beside the size (a page break
  before it) is not kept.
* *Checked* against LibreOffice 24.2.7: it reads the heights and widths of both formats, and the files it saves again
  come back with them. A width written to xlsx is in characters of the file's Normal font, which for a file of ours is
  the body text font: LibreOffice shows 150 pixels as 184. Excel was not available.
