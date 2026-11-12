---
id: D605
title: "SQL() runs a read-only query on a private in-memory SQLite database"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D605 · SQL() runs a read-only query on a private in-memory SQLite database

**`SQL(query, value...)` evaluates `query` (SQLite's SELECT, also `WITH`) over the workbook's named ranges and tables.** Every evaluation opens a fresh in-memory database; when SQLite says `no such table: Sales` the name's cells are copied in (header cells are the column names, a blank or repeated header becomes `Column<n>` or `Name_2`, a range without a header has its columns named by letter) and the query runs again. A `?` in the query is the next value after it. Quoted identifiers (`"Unit price"`) are plain SQL.

**Only reading is allowed.** An authorizer refuses everything but SELECT, reading and functions; it refuses functions whose answer differs between two calculations or that reach out of the database (`random`, `randomblob`, `zeroblob`, `load_extension`). A query is stopped after **1 second** and a result is refused beyond **100,000 rows**. Anything refused, wrong or too slow is **`#SQL!`** with SQLite's own words as the detail. One statement only.

**Notes.** What a query reads is recorded like the reads of `OFFSET`, so a query is calculated again when a table it read changes, not on every edit. Registering computes' user-defined functions as SQL aggregates is possible later (the user-function interface already knows its argument types) and is not done.
