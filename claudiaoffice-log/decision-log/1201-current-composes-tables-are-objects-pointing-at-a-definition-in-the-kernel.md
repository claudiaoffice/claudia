---
id: D1201
title: "A table is an object that points at a definition the kernel holds; computes and composes meet at TableSource"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1201 · A table is an object that points at a definition the kernel holds; computes and composes meet at TableSource

**A table in a text is an object of kind `table` (D177) whose body names a table definition by id, as a rendered container names its definition (D390). The definition, its commands and the protocol live in `claudia_core.tables`, not in composes.**

The definition (`TableDef`) holds columns and rows with ids that are never reused, the words of each cell, the merges, the look and the options. `TableSource` is a read-only protocol (id, name, version, columns, row count, text and number of a cell) that a `TableDef` implements and that a computes named range implements through its sheet, so that a linked table, a chart, `FROM` and the AI read "a table" without caring where its cells live (E9.33).

What computes and composes **share** is names (D550, D552), purposes (D604), the commands a person sees and their keys, the `cell` slots (D311), regions and this protocol. What they **do not share** is storage: a sheet's cells are positional, typed and calculated, a text's cells are words with ids. The kernel's purity test (no sheet, cell, workbook, slide or formula in an identifier) is kept: the module says `Cell` nowhere.

**Notes.** Proposed in `notes/composes-tables.md` (2026-11-18) and confirmed by the owner the same day ("kernel: in claudia_core"). Rejected: a `Table` block beside `Paragraph` in `blocks` (every place that walks paragraphs would learn a second kind of block); the definition in `claudia_composes` first (creates would have to move it later).
