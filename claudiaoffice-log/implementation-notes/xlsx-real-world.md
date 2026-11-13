# xlsx as Excel writes it today: read from the XML, edited cell by cell (D340–D342)

Branch `real-world-docs`, first of three patches. The owner supplied five real documents to find what keeps Claudia
from opening, editing and saving them. They stay out of the repository (the owner's wish); every construct they showed
is rebuilt part by part in `packages/claudia-computes-io/tests/test_xlsx_real_world.py` and in the library case
`test-documents/xlsx/beyond-claudia/excel-today`.

## What was wrong

* **The import failed** on a planning workbook (28 sheets, ~90,000 formulas): openpyxl hands an array formula over as
  an `ArrayFormula` object, and `_calculate_loaded` called `.strip()` on it.
* **One edit removed things.** `apply_edits_to_xlsx` let openpyxl save the edited sheet; openpyxl drops a worksheet's
  `extLst` (lists whose choices are on another sheet, icon sets), the `cm` mark of spilled formulas and the `vm` mark
  of a picture placed in a cell. Measured: a classroom game lost its resource list after one edit.
* **`_xlfn.` was never written**, so Excel showed `#NAME?` for `IFS`, `XLOOKUP`, `NORM.INV`… in every exported file.

## What was built (`claudia-computes-io` 0.4.0)

* `xlsx_read.py` — `open_package` (parts, sheets by the workbook's rels, shared strings, the cell formats that are
  dates), `names_and_tables`, `read_sheet` (a small `_Reading` class: `cell`, `finish` for shared formulas whose first
  cell comes later, `_place`, `_formula`), `model_formula` (the `Untranslatable` reasons `function`, `name`, `syntax`;
  `array` is decided by the cell), and the loss counting. The parser is hardened (no entities, no network).
* `xlsx_patch.py` — `written` (content → `Written(formula, value, note)`), `SheetPatch` (rows and cells indexed once;
  `put` refuses array and spill ranges, frees a shared group before its first cell changes, keeps `s`), `PackagePatch`
  (relationships, content types, `drop_calculation_chain`, `ask_for_calculation`) and `SheetNotes` (claudia's
  alternatives notes in the legacy comments and their VML).
* `excel_names.py` — the `_xlfn.` list and `with_marks` / `without_marks`, on `extensions.rename_calls`.
* `xlsx.py` keeps the public functions; `xlsx_import_losses` and `XlsxError` are new.

## Things found on the way

* **Spill members of a volatile formula** are written `<f ca="1"/>`: a formula element with no text. 7,347 such cells
  first read as `syntax` losses; they are values.
* **Cached errors as text made 2,500 formulas compute differently from Excel** (`IF(F5<>"",…)` true for the text
  `#N/A`, `SUM` skipping it). They come in as `=#N/A` now (D340). ods still reads them as text; worth following.
* **Most lost formulas are missing functions**: of the planning workbook's formulas that came in as values, 6,857
  call one (`YEAR` alone 5,397, `EDATE` 466, `MONTH` 269); 18,058 are array or spilled cells; 3,643 use names that are
  `#REF!` in the file itself. Patch 3 adds the date and finance functions.
* **VML is not XML.** Excel writes `<br>` without closing it in comment drawings, so `SheetNotes` edits the VML as
  bytes (insert before `</xml>`, remove a whole `<v:shape>` that is a note on the cell) and never parses it.
* **Stale dependents.** `apply_edits_to_xlsx` calls `current.calc.recalculate_all()` first, like `apply_edits_to_ods`:
  `WorkbookModel.store` without the server's settle leaves the values of dependent formulas stale.

## Measured on the owner's files (local only)

| | planning model | classroom game |
|---|---|---|
| import | 11 s, 47,290 live formulas, 47,289 equal to Excel's (D342 is the one) | 0.1 s, 951 live, all equal |
| one edit on every sheet | 23 sheets, lists, icon sets, spill marks and pictures in cells all kept | 4 sheets, the cross-sheet list kept |
| opens in | LibreOffice 24.2 (converted to ods with its lists), openpyxl | same |

Not run against a real Excel here; the owner's next check.
