---
id: D314
title: "Cell styles do not go to or come from xlsx in this round"
status: superseded
applies-to: computes
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: [D349]
---

# D314 · Cell styles do not go to or come from xlsx in this round

**In this round cell styles are neither exported to nor imported from xlsx.** `claudia_computes_io/xlsx.py` keeps its promise never to touch `xl/styles.xml`; an exported workbook carries its values and formulas as today, without the cell styles, and an imported workbook's cells get Body text.

**Notes.** For the later round, the proposal stays the starting point: each named style that cells use becomes one xlsx named cell style (`cellStyles`) plus the `cellXfs` entry the cells point at, so Excel shows the purpose names; on import an xlsx *named* cell style becomes a claudia style of the same name as far as the allow-list takes it, and direct formats on cells are listed as unmapped, never turned into anonymous styles (D75, D306). Owning `styles.xml` changes the round-trip promise for workbooks that came from Excel, which is why it is a round of its own. Decided by the owner on 2026-11-10 ("xlsx we do later").

**Superseded** by D349 (2026-11-13): cell styles now come from and go to xlsx and ods files; direct formats become provisional styles.
