---
id: D1533
title: "A change to what a slide gets from its layout makes the slide follow a layout of its own at once, and the person chooses: update the layout for every slide, or keep it"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1533 · A change that belongs to the layout is offered, not assumed

Moving, resizing, turning, deleting a bound object or changing its own look on a slide, and any change to another object
of the layout seen on the slide, belongs to the layout. The slide follows at once a new provisional layout, a whole copy
of the one it followed, named after it ("Two lists 2", the first number that is free; `to_name` marks that nobody named it
yet), with the change made on its copy of the placeholder. That is one Batch and one undo step
(`layout_plans.deviate_layout`). The person is then offered to *update the layout* instead for every slide that follows it
(`layout_plans.update_layout`, after an undo), or to name the new layout.

* **What does not trigger it**: typing and text formatting inside a placeholder, and free objects. (Text styles keep the
  offer of D75/D309 style deviation.)
* **Deleting a placeholder** takes the empty objects bound to it with it and frees the filled ones, which stay where they
  are (`update_layout`).
* **Taking a layout away** moves its slides to a layout the person chooses (the basic one by default), their objects to
  the placeholders with the same purpose or free where they stand, and then what is on the layout (`delete_layout`).
* **Plans, not commands.** The plans look at the document and return commands with final values; the commands decide
  nothing, so undo, replay and every client end the same way.
