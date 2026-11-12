---
id: D602
title: "A formula is bound to its names when it is compiled, and compiled again when a name changes"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D602 · A formula is bound to its names when it is compiled, and compiled again when a name changes

**Which cells `Sales[Amount]` means is worked out when the formula is compiled**, from the name's rectangle and the header cells as typed (a formula in a header shows what it showed when last calculated), and the calculator's dependency index is built from those cells. The calculator remembers every name text a formula mentions, found or not; when a name is defined, redefined, renamed, removed, grown, moved or its header changes, exactly the formulas that mention that text are compiled again and calculated.

**Retyping a header cell does not rewrite the formulas that name the column** (Excel does): `Sales[Amount]` becomes `#REF!` until it is edited. `renamed_column` exists in the rewrite module for the day that is decided; it needs the same exact-undo treatment as a table rename.

**Notes.** The alternative — resolving names while evaluating — would make every `Sales[@Units]` in a column depend on the whole column, and a formula in a table's own column would read itself (`#CIRC!`). Compiling per cell makes `Sales[@Units]` depend on one cell. Costs: a compile per user of a name when the name changes.
