---
id: D310
title: "Text boxes use the Box vocabulary; Outline is for shapes only"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D310 · Text boxes use the Box vocabulary; Outline is for shapes only

**A text box is a rectangle around words and says what it looks like with the Box facet (`background-color`, `border-*`, `padding-*`), exactly as a cell and a composes Definition do; the Outline facet (`fill`, `stroke`, `stroke-width`) is only for shapes.** The built-in `plain-shape` is split into an outline style (`fill`, `stroke`, `stroke-width`) and a shape-label paragraph style (alignment, size, line height); a text box gets a box style of its own where it needs one.

**Notes.** Narrows D178 (a shape says what it looks like in `fill`/`stroke`): D178 stays right for shapes, which are outlines in a 100 by 100 box, and is no longer the rule for text boxes, which are rectangles and so can share the Box vocabulary with cells (D304). The one cost is the split of `plain-shape` and the places that wrote an object's text properties into the object's style (`slide-style.ts` `textCss`/`pathCss`, the creates built-ins). Taken as the recommended option when the owner said "this is all good" on 2026-11-10.
