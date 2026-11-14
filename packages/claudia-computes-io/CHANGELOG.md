# Changelog of claudia-computes-io

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.5.0] - 2026-11-13

The look of cells to and from xlsx and ods (D378, D379).

### Added
- `xlsx_to_workbook` and `ods_to_workbook` bring the look of the cells as styles: the file's default look as Body text,
  its named styles by name, its direct formats as provisional styles named by what differs, and its number formats as
  the workbook's named formats; cells, rows and columns get style ranges (`cell_looks`, `xlsx_looks`, `ods_looks`,
  `odf_numbers`).
- `workbook_to_xlsx` and `workbook_to_ods` write the looks: Body text as Normal/Default, named styles as named cell
  styles, the rest as direct formats, number formats as number formats and number styles (`xlsx_write_looks`,
  `ods_write_looks`).
- `apply_edits_to_xlsx` and `apply_edits_to_ods` write a changed look: a cell, row or column whose styles changed, or
  whose style was changed, gets a new look of its own in the edited file (new `cellXfs` entries; `claudia-ce…`
  automatic styles), based on the file's named style of the same name; nothing the file had changes (D380).

### Changed
- **Breaking** for whoever reads the loss codes: `look` now has a detail, per thing a look has that no style holds
  (`rotation`, `pattern`, `center-across`, `shrink`, `number-format`, `too-many-ranges`...), counted per cell; a cell
  with only a look a style holds is no loss any more. `date` is gone for xlsx and counted for ods only where no date
  format shows the date. `xlsx_export_losses` and `ods_export_losses` count `look`: `too-many-cells`.

## [0.4.0] - 2026-11-13

xlsx files as Excel writes them today: read from their own XML, edited cell by cell (D370, D371).

### Added
- `xlsx_import_losses`: what `xlsx_to_workbook` does not show of a file, as codes with counts (`formula` with its
  reason -- `array`, `function`, `name`, `syntax` --, `date`, `error-value`, `look`, `merge`, `comment`, `chart`,
  `picture`, `conditional-format`, `validation`, `named-range`, `hidden-sheet`, `protection`...), like
  `ods_import_losses`.
- `XlsxError`: the bytes are not an xlsx file (not a zip, no workbook part).
- Defined names that are one range, and tables with a header row, come in as the model's names (D600), so the
  formulas that use them stay live.

### Changed
- `xlsx_to_workbook` reads the file with `lxml` instead of openpyxl. A formula the model cannot calculate as Excel
  does (an array or spilled formula, a function the model lacks, a name that did not come in, text it cannot read)
  comes in as the value Excel last showed, instead of failing the import (an array formula did) or calculating to
  something else. A shared formula is each cell's own formula; `_xlfn.` marks are taken off function names; an error
  Excel shows comes in as the formula that is that error (`=#N/A`), so formulas that use it get the error too; a
  date is its serial number (before, openpyxl's `datetime` became text).
- `apply_edits_to_xlsx` writes the edited cells into the original sheet's XML instead of letting openpyxl save the
  sheet, so a list that reads another sheet, an icon set, a spilled formula and a picture in a cell survive an edit
  on their sheet. An edited cell keeps its look; somebody else's comment is never removed; Excel's calculation chain
  is dropped when a formula changed, and the workbook asks to be calculated when opened. Changing a cell inside an
  array formula or a spilled range raises `UnsupportedEdit`. An unchanged model gives back the original bytes.
- Formulas written to xlsx (`workbook_to_xlsx` and edits) carry Excel's `_xlfn.` marks for the functions Excel added
  after 2007 (`IFS`, `XLOOKUP`, `NORM.INV`...): without them Excel showed `#NAME?`.

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
