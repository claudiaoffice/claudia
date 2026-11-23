---
id: D1530
title: "A layout is a definition in a list of its own, and what is on it are ordinary objects that sit on a holder that is not a slide"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1530 · A layout is a definition in a list of its own

A layout has an id and a name and no `#` reference, and its own namespace (like a style, D780): it is not a Thing. What
sits on it, placeholders and other objects (a logo, a footer), are the objects of the shared object layer (D177) whose
holder is the layout. `ObjectModel` therefore has a second list of holders, `layout_holders()` (none by default), beside
`holders()`: the slides, which are content. `all_holders()` is both and is only used to store the objects
(`objects_to_data`); reading order, numbering, search and printing walk the slides and so never see a layout's objects.

* **Record.** `Layout(id, name, origin, purpose, hidden, to_name)`; `origin` is `builtin`, `template` or `document` (as
  for a style, D780); a built-in layout can be hidden and never removed. `Layouts` keeps them by id in the order a person
  sees them, and no two have the same name, whatever the case.
* **Basic layout.** Every presentation has the built-in layout "Basic" (id `basic`) with no placeholder. A new
  presentation has one slide on it.
* **Which layout a new slide follows.** The layout of the slide before it; a slide that has none before it follows the
  first layout in the list that is not hidden.
* **State.** Schema 19: `layouts` and `slide_layouts` (slide id → layout id) are new. A state without them has every
  slide on the basic layout.
* **A layout id is not a slide id**, since holders share one namespace in the object layer: each is refused where it is
  made. A layout made by a plan has the id `l1`, `l2`… (the next free one); a layout has a name, and a place in the list.

**Why not a Thing.** A Thing has a reference and shows in every list of things; a layout is chosen from a list of layouts
only. **Why a second holder list** and not the layouts inside `holders()`: every consumer of `holders()` (printing,
search, the reading order, exports) would have had to know to skip them.
