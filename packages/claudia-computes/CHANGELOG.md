# Changelog of claudia-computes

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
