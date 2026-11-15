---
id: D620
title: "A pivot table is a named definition that compiles to SQL, not a formula"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D620 · A pivot table is a named definition that compiles to SQL, not a formula

**A pivot table is an object: a `PivotDefinition` (the source name, the row, column and filter fields, the value fields with how they are added up, and the two totals) that `compute_pivot` turns into a query for the engine of D605.** It is not a function in a cell like `SQL()`. The owner chose this on 2026-11-15 over a spilling `PIVOT()` formula: a field panel with immediate feedback is the point of a pivot (Bret Victor), the definition maps one-to-one onto Excel's pivot table and OpenDocument's data pilot table, and as a command it reaches history, undo and the `ai` user like everything else.

**The source is a name** (a table, a named range or a query result, D600, D607), never loose cells, so a pivot over a table follows the table as it grows (D603).

**Notes.** What is not decided here: where the pivot lives in the model, what owns its cells (today a formula owns a spilled result, D606, and a pivot would be a second kind of owner), and its commands. Step one is the engine only (`claudia_computes.pivot`, `pivot_sql`, `pivot_render`); the next step puts a pivot into a workbook. A pivot can be shown as the SQL it is and converted into a `SQL()` result (D624), which is the bridge to writing a query by hand. A formula `PIVOT()` stays possible later on the same engine.
