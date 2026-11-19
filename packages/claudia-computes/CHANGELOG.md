# Changelog of claudia-computes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

Heavy functions in worker processes (E4.4, D37, D1314).

### Added
- The command **`ApplyCalculated`** (kind `computes.ApplyCalculated`, not undoable): a worker's result for a heavy call
  that was deferred, applied like any other change (recalculated readers, an event, a log entry). It does nothing when
  the cell is no longer waiting for that call, so a result computed from a stale snapshot never lands.
- A `UserFunction` may declare `heavy = True`, and `heavy_above = N` to defer only once its range arguments hold more
  than N present cells. A call past that threshold is deferred instead of run inline, with its arguments frozen as a
  copy at that moment, and the cell keeps showing what it showed before.

### Changed
- An object body has one `ref` instead of a field per kind (see `claudia-core`); state schema 15.

Describing objects (BITV 1.1.1); named number formats (D378). State schema 8 → 10 (9: an object's description, 10:
the number formats). Search on claudia-search (SEC-18, CODE-18). Named ranges are things (D552) and a sheet can be renamed (E6.24):
state schema 12 → 13.

### Added
- `WorkbookModel.restyle_users(old, new)` and `CellStyles.ranges_named(style_id)`: the style ranges and objects that
  have a style, as commands that put them under another (the deletion of a style, E1.10, D226). Its built-in styles
  have `origin == "builtin"`.
- The paragraphs of `claudia-core` 0.35 have `fields` (always empty here) and `typed`, `cut`, `with_fields`.
- The paragraphs of `claudia-core` 0.33 have `generated` (always `None` here) and `with_generated`.
- The cell styles are `StyleDef`s of `claudia-core` 0.32, which have a `numbering` (always `None` here); the built-in
  styles' repr shows it, and `RemoveObject` has `ends_paragraph`.
- The cell styles are `StyleDef`s of `claudia-core` 0.30, which have a `heading_level` (always `None` here: a cell is
  no heading); the built-in styles' repr shows it.
- The help topic `computes.pivot-tables` (English and German): how to make, change and read a pivot table, and what a file keeps of one (D628).
- `NamedRange.id` (D552): a stable id, `r` + 8 hex digits from the scope and the name for ranges that were defined
  before ids (they get the same one every replay), a fresh one for a new range. A rename keeps it, so a tag in the chat
  to a range survives it. `WorkbookModel.named_things` also yields `("range", id, name)`; `thing_name` reads them.
- A range, a table and an SQL result share the name space of objects, sheets, chart tabs and slides (D550): no thing is
  named like a range and no range like a thing. Ranges among themselves keep their rule (scope and text). A range is
  renamed only with `RenameName`, not `RenameThing`.
- `WorkbookModel.rename_sheet` and `rename_thing` for sheets (E6.24): the formulas that read the sheet are printed again
  with its new name (`formula.rewrite.reprinted`), in the same step; undo puts the old text back exactly.
- Excel functions, up to rank 300 of the catalog (D480, D481): trigonometry and number theory, rounding, number systems,
  matrices (MMULT, MINVERSE, MDETERM, LINEST ...), dynamic arrays (SEQUENCE, SORT, SORTBY, FILTER, UNIQUE, VSTACK, HSTACK,
  TRANSPOSE, RANDARRAY, TEXTSPLIT), text, statistics and distributions, SUBTOTAL, AGGREGATE, dates and times, finance (RATE,
  NPER, IPMT, PPMT, XNPV, XIRR), information (TYPE, N, T, CELL, INFO, SHEET ...), LET, LOOKUP, ADDRESS. Each with a test.
- A formula can give a matrix (`claudia_computes.spill.Matrix`); the operators work cell by cell on ranges (D480).
- **Printing a workbook** (E6.19, D1001–D1009; state schema 11 → 12): `SheetPrintSetup` (orientation, scale — fit to
  width by default, fit to one page, or 10–400 %; page order; repeated rows and columns; gridlines, headings, purpose
  tints, the sheet's name in the footer, objects, skipping empty pages) and `DEFAULT_SHEET_PRINT`, stored per sheet or
  chart tab in `WorkbookModel.sheet_print` (only what differs from the default), the workbook's page in
  `WorkbookModel.print_page` (the kernel's `PageSetup`, as in composes and creates), and its `language` (the kernel's
  `SetLanguage`). The commands `SetPrintPage` and `SetSheetPrint` have exact inverses; `PrintSetupChanged` is their
  event (`{"type": "print_setup", ...}`). Older workbooks print A4 portrait, every sheet the default way. New public
  names: `SheetPrintSetup`, `DEFAULT_SHEET_PRINT`, `PrintSetupError`, `MIN_PERCENT`, `MAX_PERCENT`, `SetPrintPage`,
  `SetSheetPrint`, `PrintSetupChanged`. Repeated rows and columns do not follow `Structure` edits yet.
- `DescribeObject` is exported (it is the kernel's, `claudia_core.DescribeObject`).
- Date functions on Excel's day count, its 29 February 1900 included (D377): `DATE`, `YEAR`, `MONTH`, `DAY`, `EDATE`,
  `EOMONTH`, `DAYS`, `WEEKDAY`, `DATEDIF`. Money functions with Excel's signs: `PMT`, `PV`, `FV`, `NPV`, `IRR` (Newton's
  method, halving the interval when it does not settle). Each with a description and worked examples, in English and
  German.
- Named number formats (D378): `NumberFormat` and `NumberFormatBook`, on `WorkbookModel.number_formats`;
  `claudia_computes.numformats` reads Excel's format codes (sections, conditions, colours, locales, digits, grouping
  and scaling, percent, scientific, fractions, dates and elapsed times) and renders a number through one in English
  or German (`render`, `ENGLISH`, `GERMAN`); `describe` names what a code shows. `TEXT(value, code)`.

### Fixed
- A reference passed straight to `ROW`, `COLUMN`, `ROWS` or `COLUMNS` is no longer a dependency of the formula:
  `=COLUMNS($B$3:B3)` in B3 counted itself as a circle (`#CIRC!`), where Excel counts columns (D377).

### Changed
- `DefineName` and `RenameName` are schema 2, `AddSheet` and `AddChart` schema 3 (all carry `legacy_names`): what an
  old log holds is read with the rule it was written under.
- `=A1:A3*2` and the other operators on ranges spill cell by cell instead of `#VALUE!` (D480).
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

## [0.11.0] - 2026-11-16

### Added
- `blank(parts)` on the model (D723): an imported document is redacted in full or in parts — sheets (by id), ranges (`s1!A1:B5`), chart tabs and objects; cells are emptied, sheets and names stay. `WorkbookModel.blank_diagram` takes a chart's titles.

## [0.10.0] - 2026-11-15

Pivot tables (E6.30, D620-D622, D626): the engine, and a pivot in a workbook. State schema 13 → 14 (the pivots).

### Added
- `PivotDefinition`, `ValueField`, `PivotFilter` and `Aggregation` (sum, count, average, min, max): what a pivot is, as
  plain data (`to_data`, `from_data`, format 1). This version takes at most one row field and one column field.
- `compute_pivot(definition, tables, labels)`: reads the fields off the source, asks the SQL engine (D605) for the
  column members and then for the numbers, and gives a `PivotResult`: the grid of values, a `PivotRole` for each cell
  (corner, field, header, label, value, total) so that styles can follow it, and the SQL the numbers came from. Run by
  itself that SQL gives the same rows.
- `PivotLabels`: the words a pivot puts in its own cells (Total, (blank), Sum of ...), for a client to translate.
- `PivotError`.
- Pivots in a workbook: `WorkbookModel.pivots` (`Pivots`, `PivotEntry`: a name, a definition and the words it was made
  with), shown by a `PIVOT("name")` formula in the cell where the pivot starts, which fills its cells like a `SQL()`
  does and is calculated again whenever its source changes (D623). `create_pivot`, `update_pivot` and `delete_pivot`
  build the commands (each one step of the history, with an exact undo) out of the new `SetPivot` and the commands of
  cells and names; `PivotsChanged` is the new event.
- `PivotResult.total_row` and `total_column`; `create_pivot(..., new_sheet=)` makes the sheet in the same step;
  `pivot_to_sql` turns a pivot into the `SQL()` query it is (D624), the name staying the query's result.
- A pivot's name is a result name (D607): other formulas, `SQL()` and other pivots read it. `RemoveName`, `RenameName`
  and `DefineName` refuse to change the name of a pivot on its own; renaming the table a pivot reads renames its source.

## [0.9.0] - 2026-11-15

### Added
- `WorkbookModel.chart_cells(diagram_id)`: the cells a chart reads (a range that names its sheet, and whether its
  first row is a header), for a chart that follows a name too; `None` when it reads nothing (D462).

## [0.8.0] - 2026-11-15

Names of things (D550).

### Added
- Sheets, chart tabs and objects share one namespace: `WorkbookModel.named_things`, `thing_name`, `set_thing_name`;
  `RenameThing` renames a chart tab (a sheet is refused: its formulas would need rewriting, E6.24).
- `AddSheet.legacy_names` and `AddChart.legacy_names`: set by the upcaster for entries written before names were shared,
  so a document with a sheet and a chart tab of one name still replays.

### Changed
- `AddSheet` and `AddChart` are schema 2: a new sheet or chart tab may not take a name any other thing has.

## [0.7.0] - 2026-11-14

### Added
- `WorkbookModel.load_state`: after `core.Import` (D438) the calculator works for the workbook it is in.

## [0.6.0] - 2026-11-13

### Added
- Rendered text containers on sheets (D390): `rendered` among the object kinds (`OBJECT_KINDS`), definitions and
  their commands in the model, `state_schema` 11 (10 on the `containers` branch; renumbered at the merge,
  after the named number formats).

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
