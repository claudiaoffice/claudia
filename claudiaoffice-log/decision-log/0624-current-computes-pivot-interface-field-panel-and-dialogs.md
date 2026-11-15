---
id: D624
title: "The pivot table's interface: a field panel, a new-pivot dialog, value field settings, show as SQL"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D624 · The pivot table's interface: a field panel, a new-pivot dialog, value field settings, show as SQL

**Approved by the owner on 2026-11-15, drawn in four mock-ups** (`notes/mockups/computes-pivot-1-table-and-field-panel.svg` to `-4-show-as-sql.svg`, with a PNG each), similar to Excel's so that nobody has to learn it again, in Claudia's own language:

1. **The field panel**: floating and movable over the History & Chat dock like Search & replace; the source, a list of the source's fields with a tick each, four boxes (Filters, Columns, Rows, Values) with a chip for each field, two switches for the totals, a line naming the cells it fills. Every chip has a ▾ menu with *Move to…*, so nothing needs a mouse (BITV).
2. **Tools ▸ Pivot Table…** opens *New pivot table*: a name, the source (the table under the cursor is preselected), and a place (a new sheet, as in Excel, or a cell on this sheet). Create gives an empty pivot with the panel open.
3. **Value field settings**: the name in the pivot, sum, count, average, min or max, the number format (one of the workbook's named formats). More aggregates and "show values as" come later.
4. **Show Pivot Table as SQL…**: the query, read-only, with *Copy SQL* and *Convert to SQL query…*, which turns the pivot into a `SQL()` result of the same name in one undo step.

**Keys proposed:** Tools ▸ Pivot Table… Ctrl+Alt+T; Value Field Settings… Ctrl+Alt+E; Pivot Fields (show or hide the panel) Ctrl+Alt+M; Show Pivot Table as SQL… Ctrl+Alt+Q; Delete Pivot Table… Ctrl+Shift+Alt+E. None is used in `keyboard-shortcuts.md`; Ctrl+Alt+G is not proposed because creates uses it.

**Keys replaced (2026-11-15):** three of these cannot work (the terminal on Ubuntu, AltGr on a German keyboard); the keys now are in D627.

**Not decided:** the number formats, the filter's member list and sorting, which have no mock yet; where the pivot's own menu entries live in the web, GTK, macOS and Windows menu manifests.
