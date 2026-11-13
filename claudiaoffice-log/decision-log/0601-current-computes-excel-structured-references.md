---
id: D601
title: "Structured references are read and printed the Excel way"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D601 · Structured references are read and printed the Excel way

**`Sales[Amount]`, `Sales[@Amount]`, `Sales[@[Unit price]]`, `Sales[#Headers]`, `Sales[#Data]`, `Sales[#All]`, `Sales[[#Headers],[Amount]]` and `Sales[[Units]:[Amount]]` are formulas of computes**, read by the tokenizer (a word directly followed by a bracket) into one tree node (`TableRef`). A formula is stored in one canonical spelling (`Sales[[Amount]]` prints as `Sales[Amount]`, `[#This Row]` as `@`), like every other formula. A bracket, `#` or `'` inside a column name is written with a `'` in front, as in Excel. `@` means the row of the cell that holds the formula: outside the table's data rows it is `#VALUE!`.

**Notes.** Only the table's own name is accepted in front of the bracket (not `Sheet!Sales[...]`, not a bare `[@Col]` without the table), because a name is workbook- or sheet-scoped and needs no sheet prefix. Rewriting formulas when a table is renamed is done (`RenameName`); rewriting them when a *column header* is retyped is not (D602). Decided by the owner on 2026-11-11 ("we should support the Excel notation right away").
