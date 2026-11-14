---
id: D371
title: "An edit to an imported xlsx is written cell by cell into the original sheet's XML; nothing else in the sheet is rewritten"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: xlsx as Excel writes it today (branch real-world-docs)"
supersedes: [D220]
superseded-by: []
---

# D371 · An edit to an imported xlsx is written cell by cell into the original sheet's XML

**`apply_edits_to_xlsx` no longer lets openpyxl load and save the workbook. It changes the edited cells in the XML of
their own worksheet (`claudia_computes_io.xlsx_patch`) and leaves every other byte of the sheet's meaning alone.**
D220 kept untouched *parts* byte for byte, but a sheet with one edited cell came back as openpyxl writes a sheet, and
openpyxl leaves out what it does not know: the worksheet's `extLst` (a list in a cell that takes its choices from
another sheet, an icon set), the `cm` mark that makes a formula spill, the `vm` mark of a picture placed in a cell. One
edit took them away; on the real workbook of D370 that was 675 spilled formulas on one sheet.

What an edit changes, and nothing more:

* **The edited cell** gets its new formula (with Excel's `_xlfn.` marks, D370) and the value the model computes for it,
  or its new constant (text as an inline string, so the shared-string table stays as it was). It keeps its look
  (`s`). Emptied, it keeps its look as an empty cell, or goes when it had none. A new cell or row goes in its place in
  order; the row's `spans` and the sheet's `dimension` take it in.
* **A shared formula whose first cell is edited** first gives each of its other cells its own formula.
* **A cell inside an array formula or a spilled range cannot be changed in the file** (`UnsupportedEdit`, as for ods,
  D413): the model holds such cells as values, and Excel would see a broken range.
* **Notes for alternatives** (E6.22) are written into the sheet's legacy comments and their VML drawing, created when
  the sheet has none. Only claudia's own notes are changed or removed; somebody else's comment on the same cell stays,
  and then the alternatives are not written (they are counted as a loss at export anyway).
* **When a formula changed** (one was there or is there now), Excel's calculation chain is dropped: Excel refuses a
  chain that names a cell without a formula, and builds the chain again on load.
* **After any edit** the workbook asks to be calculated when opened (`calcPr fullCalcOnLoad="1"`): a value claudia
  changed can change what a formula on a sheet it did not touch shows, and that formula's value in the file is
  Excel's old one.

An edit that changes nothing gives back the original bytes.

**Notes.** Supersedes D220's writing half. Checked on the real workbooks of the owner (not in the repository): one
edit on each of 23 sheets of a 28-sheet planning model and on four sheets of a classroom game left every list, icon
set, spill mark and picture in place; LibreOffice and openpyxl open the results, and the lists survive LibreOffice's
own conversion to ods. Sheets added, removed, renamed or reordered are still refused, as before. The writing path no
longer needs openpyxl at all; `workbook_to_xlsx` (a new file) still uses it.
