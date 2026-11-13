---
id: D608
title: "How names, tables, SQL and spills look and behave in the web client"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D608 · How names, tables, SQL and spills look and behave in the web client

Agreed as six mocks (`notes/mockups/mock1…mock6`) before any code.

**Name Box.** The box left of the formula bar shows the name when the selection is exactly a name's region, otherwise the cell or range. Typing a name goes to it; typing an unknown valid name over a selection offers to define it; a ▾ opens the Names manager. A name is defined in a small popover (name, scope sheet/workbook, "first row is a header", "grows with its last row").

**Tables are drawn, not decorated.** A table shows a bold header, a tint by purpose (D604) and a dashed "type here to add a row" ghost row under a growing table. The header's chip opens a purpose menu for the table and for each column.

**Names manager** (Tools ▸ Names…) lists names with scope, kind, region and purpose, and renames, redefines or removes them.

**SQL editor** (Tools ▸ SQL query…) is a popover with a schema sidebar of the names and their columns, a live preview debounced by 280 ms, and Apply (Ctrl+Enter), which writes the `SQL()` formula and defines the result name in one batch (D607). A wrong table or column gets "Did you mean …?" with a one-click "Use …".

**Formula completion** offers names, then columns after `Name[`; **Tab** (not Enter) accepts, Esc closes, arrows move.

**Spilled cells** carry `"spill": true` and `"from": [row, col]` on the wire (D606). Selecting one shows a note with "Edit query…" and "Copy as values" (copies the cells as tab-separated text; it does not convert them to constants). `#SPILL!` names the blocking cell and offers "Select <cell>"; `#SQL!` shows the message. A "Move result…" action from the mock is not built.

**Popover.** Its mouse-down default is prevented so the grid keeps focus, except on `input`, `select`, `textarea`, `button` and `label`; without `label` a click on a labelled radio did nothing in Chrome.
