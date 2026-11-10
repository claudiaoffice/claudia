---
id: D178
title: "A shape says what it looks like in the SVG vocabulary — `fill`, `stroke`, `stroke-width` — not `background-color` and `border-*`"
status: current
applies-to: all
date: 2026-11-08
round: "Shapes, images and styles: one shared object layer (thirty-first round)"
supersedes: []
superseded-by: []
---

# D178 · A shape says what it looks like in the SVG vocabulary — `fill`, `stroke`, `stroke-width` — not `background-color` and `border-*`

**A shape says what it looks like in the SVG vocabulary — `fill`, `stroke`, `stroke-width` — not `background-color` and `border-*`.** A shape is an arbitrary outline in a 100 by 100 box (a circle, a triangle, a path), not a rectangle, so only `fill`/`stroke` can give it a background and a border at all; a client's property dialog is free to label them "Background" and "Border" in plain words. Both vocabularies were already in `ALLOWED_CSS`, so this is a choice about which one shapes use, not a change to the allow-list. The `plain-shape` style of all three apps now sets `fill`, `stroke` and `stroke-width`.

**Notes.** Settled by `AskUserQuestion` against the alternative of CSS `background-color`/`border-*` (which matches composes' paragraph styles but cannot express a stroke on a triangle) and against keeping both and letting the renderer pick per object kind (which would make "the same properties everywhere" two property sets). Groundwork for the next round, where all three apps get all the shapes with the same properties.
