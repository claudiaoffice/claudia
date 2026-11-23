---
id: D1475
title: "A chart becomes a slide: the slide is \"Slide n\" and the chart keeps the name it is given; on a slide, Edit ▸ Chart… puts it on that slide or a new one, from a table or a query result"
status: current
applies-to: computes
date: 2026-11-23
round: "E6.31 Slides in computes, step 3 (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1475 · A chart becomes a slide

The owner's answers of 2026-11-23 to the questions before step 3:

- **Names.** A slide made for a chart, by Edit ▸ Chart… ("A slide") or by "Move to Slide", gets the next free generic
  name "Slide n" (in the person's language), and the chart keeps its name: the name in the dialog is the chart's,
  whatever "Show as" says. The dialog starts with the next free generic "Chart n" (a read method `free_name(kind)` of
  every app that names things gives it), so that two charts do not clash by default.
- **While a slide is shown**, Edit ▸ Chart… offers "A slide" (a new slide after this one) or "On this slide"; "Data
  from" lists the workbook's tables and query results only, since a slide has no cells to select; without any, the
  dialog says to select the cells on a sheet first.
- **"Move to Slide"** has no key yet: it waits for the menu rework (`claudia-menus.xlsx`, Context menus row 25), a
  gap from the rule that every entry has a key until then.
- **No upgrade** of a stored workbook with chart tabs, and no way back for an older reader (pre-release, D1430).
- **A chart sheet in an imported file** stays skipped with a loss, as today; becoming a slide is E6.32.
- The spec wins over the story and the mocks where they differed (the chart keeps its name; the story, mock 2 and
  mock 3 were corrected).
