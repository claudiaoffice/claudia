---
id: D626
title: "A pivot in a workbook: a definition kept by name, a PIVOT() formula that shows it, a result name for its cells"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D626 · A pivot in a workbook: a definition kept by name, a PIVOT() formula that shows it, a result name for its cells

**The workbook keeps each pivot as a `PivotEntry` (its name, its `PivotDefinition` and the `PivotLabels` it was made with); the cell where it starts holds the formula `=PIVOT("name")`, and what it fills is a result name of the same name (D607).** D620 left open what owns a pivot's cells; this is the answer: the same owner as a `SQL()` result (D606), so spilling, `#SPILL!`, the recording of what it reads, live recalculation (D623), moving with inserted rows and columns, and the undo of cell contents all work as they do and nothing in the calculator is a second kind of owner. The person never types the formula and never sees a function to learn: the field panel changes the definition, the formula is what shows it, and the formula bar says what the cell is.

**Commands.** `create_pivot`, `update_pivot` and `delete_pivot` build the commands (a `Batch` of `SetPivot`, `SetCells` and `DefineName`/`RemoveName`) so that each is one step of the history and its undo is exact; they are what the server and the `ai` user use. `SetPivot` sets or takes away a definition and calculates the cells that show it again.

**The name of a pivot belongs to the pivot.** `RemoveName`, `RenameName` and `DefineName` (as a range) refuse to touch it on their own; to remove a pivot is to delete it. Renaming the table a pivot reads renames its source in the definition, and the undo is the same rename the other way. A pivot keeps its name for its life; renaming a pivot is not built.

**The grid is made again, the roles are kept.** `Pivots.result(name)` is the `PivotResult` (roles and SQL, D622) of the last calculation, not part of the document and made again when a workbook is opened; it is `None` for a pivot that failed or has no value field yet. The words (`PivotLabels`) are part of the pivot, given by the client when it is made (D622), so the cells read the same wherever the file is opened.

**Notes.** *Open:* a pivot read as a table by `SQL()` or by another pivot uses its first row as the header, which is right for a pivot without a column field and not for one with two or three header rows; a way to say "the last header row" is not built. If the formula cell is overwritten or cleared the definition and the name stay and the pivot shows nothing until the cell is put back (undo does); a pivot deleted from the panel takes both. `PIVOT("name")` typed by hand in another cell shows the same pivot there as well. A pivot's source renamed in a sheet-scoped name is not followed (only workbook-wide names are). State schema 12 → 13.
