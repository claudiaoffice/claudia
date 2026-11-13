# Changelog of claudia-computes-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.3.0] - 2026-11-13

Random numbers and alternatives in Excel and OpenDocument files (E6.22, D298, D299).

### Added
- `RANDOM("dist", …)` is written as the Excel formula that draws the same distribution (`NORMINV(RAND(),…)`,
  `LOGINV`, `BETAINV`, `GAMMAINV`, `CRITBINOM`, arithmetic on `RAND()` for uniform, exponential, weibull and pert, a
  `LOOKUP` for a discrete list), with the legacy names, which every Excel and LibreOffice version reads, and OpenFormula
  in ods. Those formulas are read back as `RANDOM`. A draw Excel has no single formula for (triangular, poisson, a
  discrete list that is not literal) is written as its value and reported as a loss (`formula`, `random`).
- Alternatives are written as the first alternative with a cell note (xlsx comment, ods annotation) that lists
  them; claudia restores them when it reads the file again and the cell still holds the first one. Reported as a loss
  (`alternatives`). `xlsx_export_losses` now reports both kinds, as `ods_export_losses` does.

## [0.2.0] - 2026-11-11

OpenDocument spreadsheets, with maximum preservation from the start (D401, D413).

### Added
- `workbook_to_ods`: a model as an ods file (every formula written as OpenFormula with its cached value; the title,
  creator and dates from a `DocumentInfo`, D411). `ods_export_losses`: what it cannot hold (formulas with no
  OpenFormula counterpart, charts, objects, layout).
- `ods_to_workbook`: the sheets, constants and formulas of an ods as a model, formulas translated to Excel text and
  recalculated by the model; repeated rows and cells are expanded, dates become serial numbers.
  `ods_import_losses` lists what the model does not show (look, merged cells, comments, charts, pictures, objects,
  validations, named ranges, filters, pivot tables, hidden rows, an untranslatable formula kept as its value...).
- `apply_edits_to_ods`: edit-and-reexport that patches the original bytes: only the cells whose content changed, and
  formula cells whose computed value changed, are rewritten (look, comment and merge of a cell stay); repeated runs
  are split, rows and columns are added where needed, sheets are added, removed and renamed; everything else, in
  `content.xml` and in every other part, is byte for byte the original's. Raises `UnsupportedEdit` for sheets in
  another order, an edited array-formula cell and a baseline that is not the file's. Reports `stale-reference` where
  removing or renaming a sheet leaves a reference in something the model does not hold (a chart, a named range).
- `to_openformula`, `from_openformula`, `Untranslatable`: the translation between Excel formula text and OpenFormula
  (checked against what LibreOffice itself writes for 110 formulas).

### Changed
- New dependency: `claudia-odf-io`.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_computes_io.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as
it stands, not a history of how it got there.

### Added
- `__version__`.
- `workbook_to_xlsx`, `xlsx_to_workbook`, and `apply_edits_to_xlsx` (D220), which raises `UnsupportedEdit` for what
  it cannot patch.
- `add_pivot_table`: a pivot table, written against openpyxl's own part layer (D147).
