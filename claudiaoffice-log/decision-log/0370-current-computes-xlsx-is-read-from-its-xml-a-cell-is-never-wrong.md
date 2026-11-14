---
id: D370
title: "An xlsx file is read from its own XML, and a cell is never wrong, only less live: a formula the model cannot calculate as Excel does comes in as the value Excel showed"
status: current
applies-to: computes
date: 2026-11-13
round: "Real-world documents: xlsx as Excel writes it today (branch real-world-docs)"
supersedes: [D220]
superseded-by: []
---

# D370 · An xlsx file is read from its own XML, and a cell is never wrong, only less live

**`xlsx_to_workbook` reads the worksheets, shared strings, defined names and tables of an xlsx file with `lxml`
(`claudia_computes_io.xlsx_read`), no longer through openpyxl, and follows the rule D413 set for ods: a cell is never
wrong, only less live.** A formula comes in as a formula when the model calculates it as Excel does. Otherwise the cell
comes in as the value Excel last showed for it, and the import counts a loss `formula` with the reason:

| Reason | What it is |
|---|---|
| `array` | an array formula (`t="array"`), including Excel 365's spilled formulas (`cm` points at the dynamic-array metadata); the cells it fills are their values too |
| `function` | a function the model lacks (on the first real workbook: `YEAR`, `EDATE`, `MONTH`, `TEXT`, `DAY`, `DATEDIF`, `IRR`, `EOMONTH`, `CONVERT`, `FORMULATEXT`) |
| `name` | a defined name or table the import did not bring along (a name of `#REF!`, a constant, a formula, several areas) |
| `syntax` | text the model cannot read, e.g. a reference into another file |

**What Excel adds to a formula in its file is taken off on the way in and put back on the way out:** the `_xlfn.` and
`_xlfn._xlws.` marks on functions Excel added after 2007 (`claudia_computes_io.excel_names`, Microsoft's list). Without
the mark on the way out, Excel itself shows `#NAME?` for `IFS`, `XLOOKUP`, `NORM.INV`... -- which the exports before this
decision did. A shared formula (`t="shared"`) becomes each cell's own formula.

**An error Excel shows is an error in the model too:** a cell with `#N/A`, `#DIV/0!`, `#VALUE!`... (a constant error, or
the value of a formula that came in as its value) comes in as the formula that is that error (`=#N/A`), so every
formula that uses it gets the error, as in Excel. Read as text, as ods still does, the first real workbook gave 2,500
formulas different results from Excel's (an `IF(F5<>"", …)` that is true for the text `#N/A`, a `SUM` that skips it).
An error the model does not know (`#BUSY!`, `#CALC!`...) stays its text.

**Defined names that are one range, and tables with a header row, become the model's names (D600)** before the formulas
are compiled, so the formulas that use them stay live. Print areas and Excel's own hidden names are not names a person
gave and are left alone.

**Dates are numbers, as in Excel:** a date cell comes in as its serial number and is counted (`date`), as every cell
with a look of its own is (`look`). `xlsx_import_losses` lists, besides, merged cells, comments (not claudia's own
notes), charts, pictures, shapes, conditional formats and lists (both the classic ones and the ones in a worksheet's
`extLst`), filters, pivot tables, sheet and workbook protection, hidden sheets and defined names that did not come in.
None of it is lost from the file (D371).

**Notes.** Found on a real planning workbook from a German utility (28 sheets, ~90,000 formulas, a public version with
sheets removed): openpyxl hands an array formula over as an object, and the import failed on it. After this decision
the file imports in about 11 seconds; 47,290 formulas are live, and all but one compute exactly what Excel stored. The
one is a `CONCAT` of a number, where German Excel writes `0,0495` and the model `0.0495` (D372). The real file is not
in the repository at the owner's wish; `test-documents/xlsx/beyond-claudia/excel-today` and
`packages/claudia-computes-io/tests/test_xlsx_real_world.py` rebuild each construct part by part. Supersedes D220's
reading half (openpyxl's object model); its writing half is D371. The XML is read with entity resolution and network
access off (SEC-15's parser half, for xlsx); the zip-size half of SEC-15 is still open.
