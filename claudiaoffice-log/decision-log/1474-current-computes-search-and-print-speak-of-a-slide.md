---
id: D1474
title: "Search and print speak of a workbook's slides: the words on a slide are searched with the cells, \"This slide\" while one is shown, and no Selection on a slide"
status: current
applies-to: computes
date: 2026-11-22
round: "E6.31 Slides in computes (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1474 · Search and print speak of a workbook's slides

- **Search.** A workbook's search goes through its tabs in their order: the cells of a sheet, and on a slide the words
  of its text boxes and the labels of its shapes, at the places creates uses (`{slide, object, source}`). The scope
  "All sheets" is called "All sheets and slides" when there are slides; while a slide is shown, "This sheet" is
  "This slide" and searches that slide, and Selection is not offered (a slide has no cells to select). A replacement
  of cells and words is one step in the history. A match on a slide shows the slide and marks the match in the words,
  as creates does; it selects nothing, so stepping through the matches holds no object from the others. Descriptions
  are not searched: a workbook's slides do not show them. This makes the search marks of D1473's slide canvas, which
  were creates' only, computes' too.
- **Print.** While a slide is shown, the print bar's contents are "This slide" and "Whole workbook" (no Selection),
  and the status line counts the sheets and the slides apart: "2 sheets and 1 slide".

**Why.** UX-72 and UX-73, which the owner asked to fix on 2026-11-22: a person who sees a slide among the sheets
expects to find the words on it, and reads "This sheet" or "3 sheets" as wrong.
