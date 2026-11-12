---
id: D607
title: "A query result is a name too"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D607 · A query result is a name too

**A name may be tied to a `SQL()` cell instead of a rectangle** (`anchor`): it is a table with a header and the purpose `result`, whose cells are wherever the formula's result is now. It is written `SalesByRegion[Revenue]` and queried as `FROM SalesByRegion`; a formula that uses it is calculated after the `SQL()` formula, and again when the result changes. Without a result (the formula failed or was cleared) it is `#REF!`. The name moves with its formula under structure edits and is taken away with its sheet.

**Notes.** Name and formula are separate commands (`DefineName` with an anchor; the formula by `SetCells`): defining one does not create the other, and deleting the formula leaves the name, which the Names manager then shows as having no result. The SQL editor does both in one batch.
