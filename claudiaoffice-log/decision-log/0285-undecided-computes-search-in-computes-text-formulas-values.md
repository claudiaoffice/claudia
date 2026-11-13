---
id: D285
title: "In computes a search looks in Text, Formulas and Values; only stored contents can be replaced"
status: undecided
applies-to: computes
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D285 · In computes a search looks in Text, Formulas and Values; only stored contents can be replaced

**Look in** has three switches. **Text**: the stored text of cells. **Formulas**: the formula as typed (`=B4*Rates!$B$3`). **Values**: what a cell shows, including the results of formulas and typed numbers and truthvalues. A find searches all three by default and says how many matches each has. **Replace changes stored contents only**: text and formula source. A value that a formula computes can be found but never replaced, because it follows from the formula; the Values switch shows a lock when Replace is open. **Replace starts with Text only**, and when the pattern also occurs in formulas the panel says so ("“€” also appears in 4 formulas, which are left alone") with the means to include them, since replacing inside a formula can change what it computes. Further switches: this sheet, all sheets, the selection. **Select the cells** turns the matches into the selection. A cell another person has locked is skipped and named (D47); a viewer can search but not replace.

**Notes.** Claude's proposal; the three scopes are the owner's ("text in cells, formula expressions or values"). A replaced formula is compiled before it is written; one that would no longer compile is shown as such in the list and left out unless the person includes it. Names, sheet names, chart titles and text objects are not searched yet (D287).
