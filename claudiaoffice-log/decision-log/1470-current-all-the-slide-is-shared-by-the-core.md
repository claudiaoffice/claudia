---
id: D1470
title: "The slide is shared by the core, as the paragraph is: its type, its frame and its anchor; each app keeps its own slides"
status: current
applies-to: all
date: 2026-11-22
round: "E6.31 Slides in computes (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1470 · The slide is shared by the core; each app keeps its own slides

A slide is a holder in creates and in computes (glossary: Slide, Tab). What both use moves into
`claudia_core/slides.py`: `SLIDE_WIDTH`, `SLIDE_HEIGHT` and `SlideAnchor` (from creates), the rule that keeps an object
on the slide (creates' `check_anchor`/`turned_anchor`, as functions), `Slide(id, name, description)` and `Slides`, a
keyed collection **without an order of its own** (that a slide which still has objects cannot be taken away is the
core's rule for every holder, `close_holder`). Each app keeps its own order (creates: the presentation, a list of ids;
computes: its tabs, D1471) and its own `AddSlide`/`RemoveSlide` (creates' carry the speaker notes and the planned time,
computes' the place among the tabs). Creates' stored state changes from a list of ids with name and description maps to
slide records in the order of the presentation (the records are `SlideModel.slides`, the order is `SlideModel.order`,
the same names as in computes): a new state schema, no upgrade (claudia is pre-release, D1430).

**Why.** The owner asked whether the slide of creates could be reused in computes (2026-11-22); it can, because a slide
is already little more than a holder of the shared object layer. A core command with optional notes would mix the two
apps; a second order inside `Slides` would be the same fact twice in computes.

Architecture A1, A2 in `notes/e6-31-slides-in-computes.md`.
