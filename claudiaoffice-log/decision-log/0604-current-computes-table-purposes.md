---
id: D604
title: "A table has a purpose, and so may each of its columns"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D604 · A table has a purpose, and so may each of its columns

**Purpose is one of `input`, `data`, `calc`, `result`**; a column without its own takes the table's. A purpose is how the table is *drawn* (a tint and a header mark, D608); it changes nothing about how cells calculate. It is part of the name, not of the cells, so it follows the table and survives a table that grows.

**Notes.** The four purposes were shown in the mocks and approved with them: input (typed by people), data (stored values), calculation (formulas), result (what a query filled). They are meant for co-thinking: which cells may I change, which does the sheet produce.
