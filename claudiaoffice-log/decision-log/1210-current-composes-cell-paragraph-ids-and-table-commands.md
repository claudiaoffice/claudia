---
id: D1210
title: "A cell's paragraph id is table/row/column, and typing in a cell is the ordinary text command"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1210 · A cell's paragraph id is table/row/column, and typing in a cell is the ordinary text command

**The paragraph of a cell has the id `<table id>/<row id>/<column id>`**, e.g. `t1/r4/c2`. Typing, deleting, styling words and attaching fields in a cell use the existing `core.InsertText` and `core.DeleteText` on that id, so authorship, per-author undo, fields, search and the AI's quoting tools (D681) work unchanged; the model answers the paragraph host questions for such an id as it does for an object's words. A merged cell's id is its top-left cell's.

The commands are `core.DefineTable`, `core.ForgetTable`, `core.SetEntries`, `core.InsertRows`, `core.DeleteRows`, `core.InsertColumns`, `core.DeleteColumns`, `core.SetRowOrder` (sorting and moving rows: it carries the order and the column it was sorted by), `core.SetColumnOrder`, `core.SetColumn`, `core.SetTableOptions` (header rows, banding, look, placement, width) and `core.SetMerge` (one rectangle; merging, resizing and splitting are the same command, and Merge Cells in an app is a batch of it with the clearing of the covered boxes); each carries final values and returns its exact inverse, and ids of rows and columns are never reused, so undo brings back the same ids.

An undo is refused (never silently wrong) when a colleague typed into a box it would destroy or put words back over, when the table was forgotten, or when rows or columns it needs are gone.

**Notes.** Ids `r…` and `c…` are not names (D550): a column's name is its header text, unique in its table, and what `Sales[Harvest]` would say.
