# Pivot tables in computes (E6.30, D620–D628)

Pivot tables in computes: step 1 the engine, step 2 a pivot in a workbook, step 3 the server API, step 4 the web client, step 5 files (ods and xlsx) and the help topic.

## Decisions this slice rests on

- **A pivot is a named definition that compiles to SQL** (D620), not a spilling `PIVOT()` formula. It reuses the read-only SQLite engine of D605–D607, so a pivot is "a special SQL query" the user can be shown.
- **Two queries** (D621): the members of the column field, then one `CASE` column per member; the total row is a `UNION ALL`. Members are written as literals, so the SQL shown is the SQL run.
- **The grid is values with roles** (D622): `PivotResult` holds the cells and a role per cell (corner, field, header, label, value, total) so the clients style by purpose (D604). Words such as "Total" and "(blank)" come from the caller (`PivotLabels`) for i18n.
- **A pivot in a workbook** (D626): a registry of definitions by name, a `PIVOT("name")` formula in the first cell as the owner of the cells (so spilling, live recalculation, moving with row inserts and undo are the existing ones), a result name for the cells. Live, no Refresh (D623). The interface is the four approved mock-ups (D624).
- **Files** (D625, D628): a pivot is written to ods and xlsx as a pivot with its cells beside it, and read back as a live pivot only when the engine makes the file's cells.

## What was built

`packages/claudia-computes` 0.8.0:

- `pivot.py`: `PivotDefinition`, `ValueField`, `PivotFilter`, `Aggregation`, `PivotLabels`, `PivotError`; validation and `to_data` / `from_data` (format 1).
- `pivot_sql.py`: member and main query generation, literals, ordering, column titles.
- `pivot_render.py`: `compute_pivot(definition, tables, labels)` returning a `PivotResult`; the column limit (1,000) and error wrapping.
- Tests in `tests/test_pivot.py`, including the exact SQL text and the property that running the shown SQL alone gives the same rows.

Step 2 (`packages/claudia-computes`):

- `pivots.py`: `PivotEntry` (name, definition, labels) and `Pivots`, the registry; the last `PivotResult` of each (roles, SQL) is kept for clients and is not part of the document.
- `formula/forms/pivot.py`: the `PIVOT("name")` form; `PivotError` becomes `#SQL!` with the message, a missing pivot `#NAME?`.
- `pivot_commands.py`: `SetPivot` and `create_pivot`, `update_pivot`, `delete_pivot`, which return one history step each.
- `model.py`, `calc.py`: state schema 13 (`pivots`), `put_pivot`, the calculator calculates the cells of a pivot again when its definition changes; renaming a table renames the source of the pivots that read it.

Step 3 (`packages/claudia-server`, `computes.py`):

- `pivots` reads every pivot for the field panel: the definition and words, the cell it starts in, the cells it fills now, `placed` (false when its cell was overwritten), the error its cell shows, and what a client needs to style the grid (`header_roles` for the header rows, `total_row`, `total_column`).
- `define_pivot` (on a sheet, or on a sheet it makes: `new_sheet`), `update_pivot`, `delete_pivot` and `pivot_to_sql` are each one history step; `pivot_sql` gives the query for the "Show as SQL" dialog. A client asks `pivots` again after a `pivots` event and after a `cells` event on the pivot's sheet.
- Turning a pivot into SQL keeps the numbers but not the upper header rows: a query has one header row. The mock-up's wording "the cells stay as they are" is true for a pivot with no column field only.

Step 4 (web client, D627):

- `web/app/lib/pivots.ts` is the logic without a component: placing a field (`placeField`, `moveChip`, `toggleField`), the chips, the source choices and a free name, and which cell of a pivot is a header, a label or a total (`roleAt`, `pivotBoxes`). `session.ts` keeps `state.pivots`, asks `pivots` again after a `pivots` event and after any `cells` or `structure` event while there is a pivot, and has `definePivot`, `updatePivot`, `deletePivot`, `pivotSql`, `pivotToSql` and `pivotMembers` (the members of a field come from `sql_preview`, at most 50).
- The field panel shows what the server has and puts a change in front of it until the server answers; a refused change is dropped and said.
- The keys of D624 were refused by the manifest's own test; D627 has the ones in use.

Step 5 (`packages/claudia-computes-io`, `claudia-computes` help, D628):

Diagram: `notes/mockups/computes-pivot-5-files-architecture.svg` (PNG alongside) — where the code is and why.

- `pivot_exchange.py` is the format-neutral part and holds every rule: `FilePivot`; writing (`written_pivots`, `sheet_cells`: the cells of a sheet with the pivot's grid as values; `pivot_positions`, `outside_pivots`); reading (`adopt_pivots`: plan, prove, apply). *Why one place:* the two formats differ in words, not in meaning, and a rule written twice drifts. The proof (`_prove`) derives the file's words ("Total Result", a German "Summe von") from the file's own cells, recomputes with the engine and requires equal cells; anything else leaves the cells alone and says `different`.
- `ods_pivots.py` and `xlsx_pivots.py` are adapters: write a `FilePivot` as XML and read XML as a `FilePivot`, with their refusals (the loss details of D628). `xlsx_pivots` builds the cache (shared items for fields on an axis or with text, numbers inline for the others, records pointing at them), the table (tabular layout, `refreshOnLoad`) and the package parts through `PackagePatch`.
- `ods.py` and `xlsx.py` call them: `workbook_to_*` writes `sheet_cells` and then the pivots, `*_to_workbook` reads and adopts (`_model_of`), `*_import_losses` and `*_export_losses` say what is not read or not written, and the edit-and-reexport paths write the cells of a pivot whose source changed (xlsx asks the caches to be read again) and count a changed definition as an unwritten change (`pivots` facet of `_unwritten.py`).
- Help topic `computes.pivot-tables` (English and German) in `claudia_computes/help/`.
- Test documents `ods/pivot-tables` and `xlsx/pivot-tables` are real files LibreOffice wrote; `scripts/odf_libreoffice_check.py` also has LibreOffice make a pivot of a model and compares its cells with the model's.
- Checked with LibreOffice only (no Excel here): LibreOffice reads our xlsx as pivot tables with the same cells for one and several values, with and without a column field; our reader reads the xlsx and ods LibreOffice writes.

## Limits of this version

One row field, one column field, five aggregates, filters by member list. The definition stores tuples, so more fields need no format change.

## Open questions

- Excel itself has not seen a written xlsx: no repair prompt is checked; the grand-total flags are read from Microsoft's documentation (D628).
- A pivot of a file with filters needs free rows above it to be written as a pivot in xlsx (`room`); Claudia does not draw filter buttons on the sheet.
- Value formats, `GETPIVOTDATA` (D481) and pivot styles by purpose (D604) are not in files yet.
- `add_pivot_table` (the spike of D147) builds a cache and a table of its own and is public API; it should use `xlsx_pivots` and be deprecated (technical debt, bugtracker).
- A pivot read as a table (`SQL()`, another pivot) uses its first row as the header: wrong for two or three header rows (D626).
- SQL groups case-sensitively, Excel does not (D621).
- Dates are serial numbers: grouping by month, quarter or year needs a conversion in the generator.
- Standard deviation, variance and median need registered aggregates.
- The source is copied into a private database for each of the two queries; a cache per source revision comes when it is felt.
- Numbering: the epic's last story was E6.23, the changelog and story use E6.30 for this work (D620–D639 block); renumber if E6.24–E6.29 are meant to be taken first.

## Next steps (not started)

1. Number formats for value fields; the filter dropdown on the sheet; a Firefox check; `GETPIVOTDATA` (D481).
2. A real Excel file with a pivot table in the test-document library (and a check that Excel opens ours).
