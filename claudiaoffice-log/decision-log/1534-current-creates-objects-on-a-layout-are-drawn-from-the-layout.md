---
id: D1534
title: "What a layout holds besides placeholders is drawn from the layout beneath the slide's own objects and is not copied onto the slides"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1534 · What a layout holds besides placeholders is drawn from the layout

A logo or a footer on a layout is one object. `SlideModel.layout_objects_of(slide)` gives what a slide shows of its
layout (everything but the placeholders, which are only places to fill); every reader draws it first. A change to it on a
slide goes through D1533 on the layout's own object. **Why not copy it onto every slide**: then a layout would have n
copies of its logo to keep equal, and a slide would own what is not its own.
