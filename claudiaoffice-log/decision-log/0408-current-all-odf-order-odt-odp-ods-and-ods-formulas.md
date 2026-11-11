---
id: D408
title: "The OpenDocument formats come in the order odt, odp, ods, and ods formulas are translated to OpenFormula and back"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D408 · The OpenDocument formats come in the order odt, odp, ods, and ods formulas are translated to OpenFormula and back

**odt first, then odp, then ods; each gets the three paths of D403.** For ods the formulas the model implements (D12: Excel's language) are translated to OpenFormula and back; a cell always gets its cached value written next to the formula; a formula that cannot be translated is written as its value alone and counted as a loss. odp is done (D412), ods too (D413, D414).

**Notes.** ods is last because the formula translation is the hard part, and because the loss list for a spreadsheet (charts, pivot tables, cell styles, D314) needs the most thought. Writing the cached value always means a program that does not recalculate still shows the right numbers. The owner agreed to this order on 2026-11-11.
