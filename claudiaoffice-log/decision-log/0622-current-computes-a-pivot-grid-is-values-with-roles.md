---
id: D622
title: "A pivot's grid is plain values, each with the role it plays; its words come from the client"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D622 · A pivot's grid is plain values, each with the role it plays; its words come from the client

**`compute_pivot` gives a `PivotResult`: the rows of values, a `PivotRole` for each cell, how many rows are header, and the SQL.** The roles are `corner` (the value's title, when there is one value under a column field), `field` (Region, Quarter), `header` (a column member, a value's title, a blank that belongs to the header), `label` (a row member), `value`, and `total` (the total row and column and the label of the total row). How each looks is a matter of styles by purpose (D604), not of the engine.

**The layout is Excel's compact one.** Without a column field one header row (the row field's name, then the value titles); with one value under a column field two (the value's title and the column field's name; then the row field's name, the members and `Total`), with several values three (the field's name; the members, each over its values; the row field's name and the value titles). The result can fill cells like a `Table` (`height`, `width`, `value_at`) or be given as a `Matrix`.

**The words a pivot writes into cells** (`Total`, `(blank)`, `Sum of Amount`) are a `PivotLabels` the caller passes in, in English by default, so that the server's pivot is the same in every language and each client says it in its own.

**Notes.** A pivot with no value field gives an empty result: there is nothing to add up yet.
