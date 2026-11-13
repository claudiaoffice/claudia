# Changelog of claudia-computes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.3.1] - 2026-11-13

Search and replace in workbooks (E6.20, D285, D286). No change to `__all__`.

### Added
- `claudia_computes.search` (a module, not part of `__all__`): `scan` looks for a compiled search in the *text*, the
  *formulas* and the *values* of a workbook (on every sheet, one sheet or a selection, within a time limit), listing
  matches with the kept parts and what a replacement would make of each, and the cells left out with the reason;
  `plan_replacement` says which cells a replacement would change and which it skips (held by somebody else, a formula
  that would no longer read, a text that would be too long); `replace_command` makes it one `Batch` of `SetCells`,
  one per row and run of columns, that stores the cells as they will be, never the pattern. The part `cellref`
  (`B4`, `$A$2`) is computes' own.

## [0.3.0] - 2026-11-12

The styling-suite plan, steps 1.1 to 2.6 (D300–D318).

### Added
- The built-in **`plain-box`**, a `box` style without properties: the box of a text box on a sheet (D310).
- **Cell styles** (E6.13, D307, D311, D313): `claudia_computes.cellstyles` — `CellStyles`, a sheet's style ranges
  for the `box` and the `words` slot of its cells, in four layers by shape (`sheet`, `column`, `row`, `range`,
  `layer_of`), non-overlapping inside a layer, looked up most specific first and `body-text` where no range
  covers a cell; `MAX_STYLE_RANGES` per sheet. `Sheet.cell_styles`, in snapshots.
- `SetCellStyle(sheet, slot, layer, area, pieces)` and `SetCellStyle.put(sheet, slot, area, style)`: a logged,
  undoable change of one slot and layer, with regions (cell locks hold it) and a refusal of a style that does not
  fit the slot. Event `CellStylesChanged`.
- The cell styles a workbook starts with (D313): **Header**, **Input**, **Result**, **Note**, paragraph styles on
  Body text written in palette roles.

### Changed
- **Breaking:** `plain-shape` is an `outline` style (`fill`, `stroke`, `stroke-width` only, no parent); its words'
  centring moved to the new built-in **`shape-label`**, based on Body text. `plain-image` is a `box` style.
- **Breaking:** `WorkbookModel.restructure` also moves the style ranges and returns the pieces that lay on
  deleted lines as a fourth value; `Structure`'s undo and `RemoveSheet`'s undo put the styles back.
- `WorkbookModel.style_in_use` counts style ranges.
- The last action wins (D317): `CellStyles.plan` and `SetCellStyle.applying(model, sheet, slot, area, style)` turn
  one styling action into the replacements that give every cell of the area the style (or, with `None`, clear it
  so that what lies beneath shows through), in one undo step. `SetCellStyle.put` writes one layer only.

## [0.2.0] - 2026-11-11

Names, tables and `SQL()` (D600–D609).

### Added
- Names: `DefineName`, `RenameName`, `RemoveName` commands (with `RestoreNames`, their shared inverse); a name is a
  region (`CellRegion`) or a `SQL()` anchor, with an optional header, growth with its last row, a purpose per table
  and per column, and a workbook or sheet scope. The registry is `WorkbookModel.names`; `{"type": "names"}` events
  announce changes.
- Excel structured references in formulas: `Sales[Amount]`, `Sales[[#Headers],[Amount]]`, quoted identifiers.
- `SQL(query)`: the first spilling function — SQLite in memory, read-only, one statement, a 1 s limit and 100,000
  rows; its result is a table that can be named. New errors `#SQL!` and `#SPILL!`.
- `ChartSpec.source` and `source_scope`: a chart may read a named table instead of a range (exactly one of the two).
- Spilled cells are returned by `Sheet.view` with `"spill": true` and `"from": [row, col]`.

### Changed
- **Breaking:** `ChartSpec.range` is optional; code that read it unconditionally must check `source` too.
- `Sheet` and `WorkbookModel` gained the members the snapshot lists; see `tests/api/claudia_computes.json`.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_computes.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as it
stands, not a history of how it got there.

### Added
- `__version__`.
- The workbook: `WorkbookModel` (`state_schema` 6) with its `Sheet`s, typed cell `Content` (`content_of`), chart tabs
  (`Chart`), cell-anchored floating objects (`CellAnchor`, `SheetObject`; `OBJECT_KINDS`, `MIN_OBJECT_SIZE`,
  `MAX_OBJECTS_PER_SHEET`), its style book (`BUILTIN_STYLES`, `DEFAULT_STYLE`, `builtin_styles`) and palette.
- References: `CellRef`, `RangeRef`, `SheetId`, `column_name`, `parse_range_ref`, `RefParseError`, and the structural
  edits `InsertRows`, `DeleteRows`, `InsertCols`, `DeleteCols`; `CellRegion`, a region that moves with them.
- This app's commands: `AddSheet`, `RemoveSheet`, `SetCells`, `Structure`, `ResizeLines`, `AddChart`, `RemoveChart`;
  what typing into a cell means (`parse_input`).
- Charts: `ChartSpec`, `CHART_KINDS`, `ChartError`.
- State events `ChartsChanged`, `DiagramsChanged`, `ImagesChanged`, `ObjectsChanged`, `ShapesChanged`.
- The function catalogue: `FunctionHelp`, `function_catalog`, `search_functions`, `get_function`.
- Re-exported from `claudia_core`, so the package names everything a workbook can do: the shared object commands and
  types (`AddObject`, `MoveObject`, `ResizeObject`, `RotateObject`, `RemoveObject`, `SetSnap`, `SetText`,
  `SetParagraphStyle`, `DefineImage`/`ForgetImage`, `DefineShape`/`ForgetShape`,
  `DefineDiagram`/`UpdateDiagram`/`ForgetDiagram`, `ObjectBody`, `VisualObject`, `ObjectSet`, `DiagramDefinition`,
  `Paragraph`, `Run`, `paragraph_for`).

### Fixed
- `__all__` named `column_name`, `content_of`, `parse_input` and `parse_range_ref` twice. The surface is the same.
