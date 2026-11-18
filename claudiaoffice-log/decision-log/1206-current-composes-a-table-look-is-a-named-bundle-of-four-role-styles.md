---
id: D1206
title: "A table look is one named bundle that fills the four role slots of a table, as a cell style fills both slots of a cell"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1206 · A table look is one named bundle that fills the four role slots of a table, as a cell style fills both slots of a cell

**A table points at one look, by name. A look names four styles: the header, the body, the band (every second body row, optional) and the total row.** Each is a paragraph style, which holds a box and words, so it fills both slots of the `cell` thing (D311, D315) in one step; "change the box only" works as in computes (D309). There is no formatting of a single cell: a person changes a table's look, or a style, never a cell (D306).

The text starts with three built-in looks (`TABLE_LOOKS`; custom looks come later, as a later decision): **Rules** (the default: a heavy rule above the header and below the total, a thin rule under the header and above the total), **Grid** (thin rules everywhere) and **Plain** (none). Their twelve styles (`table-rules-header` … `table-plain-total`) are built-in styles of the text, so a change to Body text reaches them (D73).

**Notes.** Asked as "four role slots, or one named bundle that sets all four at once, as list schemes do": the owner chose the named bundle (2026-11-18). The table options offer the looks by name and a band switch; a person who wants another look restyles one of the twelve styles in All Styles for now. File formats write the looks' box properties with a table's cells, so the style-by-style loss check leaves them out (`TABLE_STYLE_IDS`).
