---
id: D609
title: "A chart can read a named table instead of a range"
status: current
applies-to: computes
date: 2026-11-11
round: "Names, tables and SQL() (branch named-ranges-sql)"
supersedes: []
superseded-by: []
---

# D609 · A chart can read a named table instead of a range

**A `ChartSpec` reads exactly one of `range` or `source`** (a name, with `source_scope` for a sheet-scoped one); giving both or neither is an error. A named source always has a header row: the header gives the series names and the first column the categories. The chart follows the name, so it follows a growing table and a changing `SQL()` result.

**A name that no longer exists gives an empty figure, not an error**: deleting a name must not make the document fail to open or the chart tab fail to draw.

**Limitation, deliberate for now:** renaming a name does *not* rewrite the sources of charts that read it, so such a chart goes empty until it is pointed at the new name. Formulas are rewritten (D602); charts are not.

**Web.** The insert-chart dialog lists the document's names ("Data from") with "Pick cells instead…" for a range. Bar is the only kind; Line and Scatter are shown disabled as "soon". A chart that reads a name is redrawn on any cell change and on any change to the names, because the client cannot tell which cells a name covers.
