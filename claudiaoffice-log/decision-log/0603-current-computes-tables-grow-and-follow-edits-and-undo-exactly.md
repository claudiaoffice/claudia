---
id: D603
title: "Tables grow with the row typed below them, follow structure edits, and every name change has an exact undo"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D603 · Tables grow with the row typed below them, follow structure edits, and every name change has an exact undo

**A table that `grows` takes in a row when a cell is typed in the row right below it, in one of its columns** (several rows pasted below at once make it that many rows longer). Clearing a cell does not grow it and nothing shrinks it by itself. Inserting rows inside a table makes it longer, deleting rows inside shorter, deleting all of it removes the name.

**Every command that changes a name returns an exact inverse**: `DefineName`, `RemoveName`, `RenameName` (with the formulas it rewrote, as typed), `SetCells` that grew a table, `Structure` that moved or removed one, `RemoveSheet` that took the names on its sheet. They all hand `RestoreNames` the names as they were, so undo, redo, replay of the log and per-author undo (`shifted_by`: a name command is not shifted across an edit of the sheet it is on, nor across another command on the same name) need nothing special.

**Notes.** The snapshot schema of a workbook is now 7 (names). Older snapshots are caches (D15) and are rebuilt from the log.
