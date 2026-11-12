# OpenDocument spreadsheets (and presentations): ods and odp on `claudia-odf-io` (D411–D414)

Continues `odf-odt-import-export.md`. Same mechanism: parse to *find*, splice bytes to *change*; no edit → identical
bytes. For a spreadsheet the hard parts were the repeated rows and cells of ODF and the formulas.

## What was built

**`claudia-computes-io` 0.2.0** — `ods.py` (`ods_to_workbook`, `workbook_to_ods`, `apply_edits_to_ods`,
`ods_import_losses`, `ods_export_losses`) and `openformula.py` (`to_openformula`, `from_openformula`, `Untranslatable`).
**`claudia-odf-io`** gained `NS["of"]`/`calcext` and a multi-piece `XmlPart.replace`. The server's `export_office` takes
`"ods"`; the Export dialog lists it. **`claudia-test-documents` 0.2.0** — `ADAPTERS["ods"]`, four ods cases.

## How `ods.py` is organised

* `_scan_table` reads a table into `(row, column) → content` with the span of each cell kept; repeats are expanded (rows
  and cells), covered cells skipped, `_MAX_CELLS` guards a hostile file.
* `_read_cell` / `_cached` turn a cell into content: formulas translated (`from_openformula`) or, if untranslatable, the
  cached value with a loss. Dates → serial, times → fraction of a day.
* `_Patch` is the edit: `_patch_table` → `_columns` (declare missing columns), `_patch_rows`, `_append_rows`,
  `_patch_cells` (find the changed positions; `_segments` splits a repeated run around them; `_rewritten` makes the new
  cell with `_like(old)`), then `_add_tables`, `_remove`, `_stale`. Its first line is `current.calc.recalculate_all()`:
  `WorkbookModel.store` without `settle` leaves dependents stale, and the patcher compares computed values to decide
  which formula cells need their cached value refreshed (`refresh=True`: keep `table:formula`, rewrite the value
  attributes).
* A baseline check (ids, names and cells equal a re-import of the file) comes first; a baseline that is not the file's
  raises `UnsupportedEdit`.

## Things that were found on the way

* **`of:` must be declared** (`xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2"`) or LibreOffice reads every
  formula as `Err:510`. Found by converting a model-made file to CSV; fixed in `NS`.
* **A copied element carries only the namespaces it uses** (lxml `deepcopy`), so a copied cell came out as `ns0:`/`ns1:`.
  `_like()` builds a fresh element with the full `nsmap` and copies attributes and children.
* **Formula translation was checked against LibreOffice**, not against the spec: 110 formulas written by LibreOffice 24.2.7
  from an xlsx; differences only XLOOKUP/XMATCH and `1.5E3` (D414).
* **The LibreOffice check found a real gap:** a formula with no translation (a union) keeps its formula and its old cached
  value after an edit of what it depends on; LibreOffice recalculates on load so the *program* is right, the *file's cache*
  is stale. Documented in D413; the fixture's union now sits on cells no edit touches so every cell can be compared.
* **Regenerating all fixtures** with `_build_fixtures.py` rewrote the docx/pptx/xlsx sources (zip timestamps/ordering from
  the library versions): only the one fixture is rebuilt when a single one changes.
* **LibreOffice-written ods fixtures** come from converting the xlsx fixtures (`soffice --convert-to ods`): cells and a
  formula, a chart (`Object 1/…` sub-document plus `ObjectReplacements/Object 1`), a picture (`Pictures/…`).

## How it was checked

Unit tests (`test_ods.py` ~150 incl. a random-edit property test, `test_openformula.py`; ods.py ≈ 98 % coverage, openformula
91 %), the server export tests, four library cases (the preserve stage verified to fail when an expectation is wrong), and
LibreOffice 24.2.7: `scripts/odf_libreoffice_check.py` (31 of 31) converts every edited and new file to xlsx and compares every
cell with the model's value (numbers with a tolerance, dates as serials, errors as codes).

## Open

* Loss-list and import screens; cell styles, widths and heights (E6.13, E6.16, E6.18); charts as content.
* Array-formula cells are read as values and cannot be edited (`UnsupportedEdit`).
* References in unmodeled objects after a sheet is removed or renamed are only reported (`stale-reference`).
* Stale cached value of an untranslatable formula after an edit (D413).
* XLOOKUP/XMATCH as `COM.MICROSOFT.*` not verified in a newer LibreOffice.
