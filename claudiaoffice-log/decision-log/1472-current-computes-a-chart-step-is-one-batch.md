---
id: D1472
title: "One module builds every chart step as one undo step: a chart on a new slide, Move to Slide, and removing objects (a chart takes its spec along, a slide goes with its last object)"
status: current
applies-to: computes
date: 2026-11-22
round: "E6.31 Slides in computes (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1472 · A chart step is one `Batch`, built in one place

`claudia_computes/chart_steps.py` returns one `Batch` (one undo step, all or nothing) for:

- **a chart on a new slide:** the chart's definition, a slide right after the current tab with the name typed in the
  dialog, the chart filling the slide's frame;
- **Move to Slide:** a slide right after the sheet, named with the next free "Slide N" (the chart keeps its name, which
  people may already use), `MoveObject` onto it, `ResizeObject` to the frame; undoing it puts the chart back at its
  cell and size and removes the slide **only if it is empty** (a colleague may have put something on it);
- **removing objects:** the objects, the definition of each chart among them (one `ChartSpec` per chart object; there is
  no copying of charts yet), and every slide left empty.

The server's methods, cut and delete, and later the ai, use it, so the rules are written once.

**Why.** The owner decided that a chart is an object specified by its data, kind and titles, deleted with it (Q2 and Q11
of the chart session), that a slide exists only for its chart and goes with its last object (Q20), and how naming and
undo work (Q1 and Q4 of the review of `specs/computes/slides.feature`).

Architecture A5 in `notes/e6-31-slides-in-computes.md`.
