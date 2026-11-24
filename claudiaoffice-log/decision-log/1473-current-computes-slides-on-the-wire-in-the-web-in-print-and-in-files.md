---
id: D1473
title: "Slides on the wire, in the web client, in print and in files: insert_chart and move_to_slide, one slide canvas for creates and computes, a slide printed as creates prints one, written as a sheet"
status: current
applies-to: computes
date: 2026-11-22
round: "E6.31 Slides in computes (branch e6-31-slides-in-computes)"
supersedes: [D204]
superseded-by: []
---

# D1473 · Slides on the wire, in the web, in print and in files

- **Wire.** `insert_chart(definition, show_as, place)` defines and places a chart in one step (D1472), where D204 kept
  defining and placing apart; `move_to_slide(object)`; computes' `remove_object` goes through D1472's removal.
  `add_chart`, `remove_chart` and the event `charts` go; the event `tabs` and the stored keys `tabs` and `slides` come.
  `define_diagram` and its relatives get the chart names of E1.18 in the last step of E6.31.
- **Web.** `SlideHost` is what `SlideCanvas.vue` needs of a session; creates' and computes' sessions implement it and
  share the slide's helpers, and what only creates has (snapping to the grid, the agenda, search marks, the fence for
  containers) is optional. Computes shows `SlideCanvas` and the object tools for a slide tab, without speaker notes and
  Present, and one list of tabs. A new slide is shown with nothing selected; when a slide goes, the tab before it is
  shown (the one after it, if it was the first). A viewer sees slides; "Move to Slide" is shown but cannot be chosen.
- **Print.** A computes slide is printed by the layout library's `layoutSlides`, as one landscape page, the charts as
  their pictures; printing the workbook prints each slide between the sheets, in tab order.
- **Files.** `claudia_computes_io/slide_plan.py` writes a slide to ods and xlsx as an empty worksheet with its objects
  on it (scaled from 1600 × 900 to the size a chart tab has today), with the loss "The slide “…” was written as a
  sheet: a workbook in this format has no slides." What was a slide is read back as a sheet. *Replaced by D1477: a
  slide is a tab of its own with its objects where they were, and nothing is reported.*

**Why.** Agreed with the owner on 2026-11-22 (architecture A6 to A9; answers Q2, Q3, Q5, Q6, Q7 of the review of
`specs/computes/slides.feature`). Defining and placing a chart in one call supersedes D204: the dialog's chart is one
undo step, not two or three.
