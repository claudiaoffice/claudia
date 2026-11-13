---
id: D600
title: "Named ranges and tables are one concept"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D600 · Named ranges and tables are one concept

**A name points at cells; a name whose first row is a header is a table.** The same record (`NamedRange`) holds both: a rectangle on one sheet, whether its first row names the columns (`header`), whether it takes in the row typed right below it (`grows`), and its purposes (D604). A table is queried as `FROM Sales` (D605) and written `Sales[Amount]` in formulas (D601); a plain range is written `Rate`. A bare table name in a formula means its data rows, as in Excel.

A name has a **scope**: the whole workbook, or one sheet. On its sheet a sheet-scoped name shadows a workbook name of the same text. Names are compared without regard to case. A name is one word (letters of any alphabet, digits, `_`, `.`) that is not a cell address and not `TRUE`/`FALSE`, so a formula can always tell a name from a cell.

**Notes.** Why one concept: the owner's demo had SQL over "named ranges with header cells"; two concepts (range, table) would make every feature ask which one it was given. The CellRegion of E1.5 stays the thing that *moves* with edits; a name's rectangle follows structural edits the way a reference does (rows inserted inside it make it longer, deleted inside it shorter, all of it deleted removes the name), and an undo puts the name back exactly (D603). Decided by the owner on 2026-11-11 ("named ranges and tables are the same concept, if the named range has a header").
