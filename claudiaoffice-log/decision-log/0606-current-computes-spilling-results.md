---
id: D606
title: "A formula that gives a table fills the cells below and beside it, and owns them"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D606 · A formula that gives a table fills the cells below and beside it, and owns them

**`SQL()` as the whole formula spills**: its cell shows the first cell of the result (the header of its first column), the rest of the header row and the rows below fill the cells right and below. Those cells show values, are not stored in the document, are not written by a command (writing one is refused, telling the person to change the query), and are owned by the formula: they empty when the formula goes. If a cell in the way holds something of its own, or another result, the formula shows **`#SPILL!`** and says which cell is in the way (`SalesByRegion needs A3:B7, but B5 holds a value`); it is calculated again when anything in that area changes. `SQL()` inside another formula gives the first value of the first row (`#N/A` with no rows).

**Calculation:** formulas that read spilled cells may be calculated before the formula that fills them, so after a round that changed a result the formulas that read it are calculated again, until nothing changes (at most 20 rounds). A structure edit clears results on its sheet and everything is calculated, which puts them where they belong.

**Notes.** A client gets a spilled cell as `{"t": ..., "v": ..., "spill": true}`. Selecting a spilled cell and editing it is the client's cue to offer "Edit query…" and "Copy as values" (D608).
