# Changelog of claudia-computes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

Describing objects (BITV 1.1.1). State schema 8 → 9. Search on claudia-search (SEC-18, CODE-18).

### Added
- `DescribeObject` is exported (it is the kernel's, `claudia_core.DescribeObject`).

### Changed
- Object bodies carry `description` and `decorative`; see the core changelog. A snapshot written before is retired and
  rebuilt from the log.

### Changed
- `claudia_computes.search` (not part of `__all__`) is computes' side of `claudia_search`: `workbook_texts` offers a
  workbook's texts with their cell as `at` (`cell_at`, `cell_of`), `scan_workbook` and `plan_replacement` run until a
  `deadline`, `leave` is a list of `(at, number)`, and `Hit`, `LeftOut`, `Change`, `Skip`, `Plan`, `Scan` and
  `MAX_LISTED` are claudia-search's. A plan no longer carries the cell content; `replace_command` makes it. The package
  depends on claudia-search.

### Added (UX-33)
- `WorkbookModel.setup_commands`: a new workbook starts with its first sheet, `s1` "Sheet1", made by the server as nobody's undo step (UX-33). The web client no longer adds it.

## [0.5.0] - 2026-11-13

The function catalog can be said in another language (E13.8, D323); the package still carries no catalog. An outcome
input is named by its named range (E6.21).

### Added
- `FunctionHelp.translated(translate)`: the entry with its description, tooltip and help text said by the function
  `translate` (the identity gives the same entry); `FunctionHelp.examples` holds a library function's worked examples.
- `translatable_texts()`: every text a translator is given for the catalog (the descriptions, the notes of examples and
  the two wordings of an example, `functions.base.GIVES` and `GIVES_WITH`).
- `Bound.get_tooltip(translate)` and `Bound.get_help(translate)` take the same function, and
  `functions.base.example_lines(examples, translate)` puts a function's examples into lines of text.

### Changed
- The outcome table names an input by its named range when the input cell is exactly one (`OutcomeTable.inputs[].label`),
  and only otherwise by the text to its left (E6.21).

## [0.4.0] - 2026-11-13

Random numbers, alternatives and following a computation (E6.21–E6.23, D291–D299).

### Added
- **`RANDOM(...)`** (E6.22, D291–D293): the same numbers for every user, because a number is a function of the
  workbook's seed, its draw number, the cell and the position in the cell's call (`claudia_computes.draws`, BLAKE2b),
  never of a clock or a generator's state. `RANDOM()` is Excel's `RAND()`; `RANDOM("dist", params…)` draws from
  uniform, normal, lognormal, triangular, pert, exponential, weibull, beta, gamma, binomial, poisson or a discrete
  list of values with weights (`claudia_computes.distributions`, quantile functions in `claudia_computes.special`),
  optionally cut to `low`/`high`. `Resample` (relative, so undo works after colleagues' changes) and
  `SetRandomSeed` are logged commands, `RandomChanged` an event; workbook state schema 8 keeps seed and draw number.
- **Alternatives** (E6.21, D294–D296): an input cell may hold `{a, b, c}` (stored as `=ALTERNATIVES(a,b,c)`, or
  `=SCENARIOS("name", a, b, …)` with a name), each alternative a value or a formula. `Sheet.alternatives` and
  `Sheet.outcomes` are derived: for every cell that depends on alternatives, the value for each combination, its
  median and spread, computed by running the calculation over the cells that take part (`claudia_computes.outcomes`;
  above 10 000 combinations a seeded sample, with common random numbers). `WorkbookModel.outcome_table(sheet, row,
  col, combine)` lists every outcome with the alternatives behind it and a sensitivity per input (`combine="pair"`
  takes the first alternatives together, the second ones, …).
- **Follow a computation** (E6.23, D297): `WorkbookModel.trace(sheet, row, col, reach, window)` gives the cells connected
  to a cell, each as `input`, `calc` or `output`, cut to the visible window, with counts for other sheets
  (`claudia_computes.trace`). A view, not an edit.
- New public names: `Resample`, `SetRandomSeed`, `RandomChanged`, `AltInput`, `OutcomeRow`, `OutcomeTable`, `Swing`,
  `Trace`.

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
