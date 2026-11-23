---
id: D1536
title: "A provisional layout that nobody follows and nobody named is taken away by the step that made it unused"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1536 · Provisional layouts nobody follows go with the step

A deviation (D1533) makes a provisional layout, marked `to_name`, with a name like "Two lists 2". The owner decided
that when no slide follows it any more and nobody gave it a name, it is removed automatically, and that the removal is
part of the step that made it unused, so that undo brings it back with its objects and its slide.

* The plans `set_layout_command`, `deviate_layout` and the new `remove_slide_command` (`layout_plans.py`) end with the
  removal of the layout the slide leaves (its objects, then `RemoveLayout`) when it is provisional and no other slide
  follows it. One batch, one undo.
* A layout a person named (`RenameLayout`, which clears `to_name`) stays, followed or not.
* `delete_layout` moves slides with the plain step; the layout it takes away is removed by the plan itself.
* `settle` removes nothing, and `SlideModel.layouts_to_choose()` only leaves out hidden layouts.
* A client that sends the plain `SetSlideLayout` or `RemoveSlide` can still leave such a layout behind; it shows in the
  list with its name, and a person can name or delete it. The clients use the plans.

Considered and rejected: removing in `settle` (not a step in the log, so undo could not bring the layout back); hiding
the layout (the first draft of this decision), which left layouts nobody could see in every saved deck.
