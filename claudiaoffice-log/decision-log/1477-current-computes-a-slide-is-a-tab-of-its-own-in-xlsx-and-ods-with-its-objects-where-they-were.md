---
id: D1477
title: "A slide is a tab of its own in an xlsx or ods file, its objects where they were (one slide unit is one pixel, a setting of the export); charts and pictures are placed by one shared plan, and the duplicated chart code of the two formats is one"
status: current
applies-to: computes
date: 2026-11-24
round: "E6.31 Slides in computes, step 5a (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1477 · A slide is a tab of its own, its objects where they were

This replaces the bullet **Files** of D1473; the rest of D1473 stands.

- **Size.** One slide unit is one pixel of the tab: a slide of 1600 × 900 covers 1600 × 900 pixels from the tab's
  corner. The scale is not a constant of the code but a setting of the export (`SlideSize(px_per_unit=1.0)`), so that
  a later dialog can ask for another size (owner, Q1).
- **Place.** An object is placed at its exact position: the cell its corner falls in, and the offset in that cell
  (xlsx `colOff`/`rowOff`, ods `svg:x`/`svg:y` from the tab's corner). An object on a sheet is placed as before.
- **No message.** Writing a slide as a tab is not reported (owner, Q5). The loss `slide` goes.
- **Tabs.** The tabs of the file are the model's tabs in their order, sheets and slides; a slide's tab has the slide's
  name, written as a sheet may be called in Excel, and no cells. The model is no longer copied with its slides turned
  into sheets (`slide_plan.with_slides_as_sheets` goes).
- **One plan, no duplicates.** `claudia_computes_io/_placed.py` says which tabs a file has and where each object of the
  workbook is on its tab, in pixels; the pictures (`_pictures.py`) and charts (`_charts.py`) of both formats are taken
  from it, and each format has one function that places a drawing on a tab. The definition of a chart object
  (`definition_of`) and the reading of a file's charts into the model are each written once for both formats.

**Why.** Agreed with the owner on 2026-11-24 (answers Q1, Q2, Q5 and the architecture of step 5). Scaling a slide down
and snapping its objects to the nearest cell lost where they were and made a slide look unlike itself; the two
formats had grown the same chart code twice.
