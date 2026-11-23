---
id: D1531
title: "A slide object bound to a placeholder keeps the place, size, turn and look of the placeholder as its own, the layout is the truth, and `settle` repairs the copies"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1531 · A bound copy follows its placeholder

An object on a slide that is filled into a placeholder stays a complete object: it has its own x, y, width, height,
turn and look, so that the slide stands alone and every reader of the slide (print, export, a client) needs no layout to
know where it is. What marks it is `SlideAnchor.bound_to_placeholder`, the id of the placeholder on the layout its slide
follows. The values are a copy, and the layout is the truth.

* **Repair in `settle`.** After every top-level command (also after one that was rolled back, after undo and in replay)
  `SlideModel.settle` makes every bound object equal to its placeholder, and tells the views of the slide
  (`ObjectsChanged`). It never refuses, and it is derived from the state alone, so undo, redo and replay come to the same
  document without the repair being a step of its own.
* **Free where it stands.** A binding to a placeholder that is not on the layout its slide follows (gone, or of
  another layout) does nothing: the object keeps where it stands, and nothing is cleared, so that undoing what removed
  the placeholder binds the object again (`SlideModel.placeholder_of` is the binding that counts). A person's own
  rebinding (`SetSlideLayout.rebind`, which carries the old bindings for its inverse) does clear one.
* **Only the layout changes them.** A command that would change the place, size, turn or look of a bound object is
  refused ("change the layout instead", `SlideModel.replace_object`, which compares the object before and after, so a
  copy that lags behind in the middle of a Batch can still be written in); setting or clearing the binding is an
  ordinary change, and an object added with a binding gets the place of its placeholder in `settle`. A move,
  resize or turn says where, not what the object is for or bound to (`ObjectModel.placed_at`).
* **The look is copied only between objects of the same kind** (a picture put into a text placeholder keeps its own).
* **Cost.** Settling looks at every object once per command to find the bound ones. Measured on a deck of 200 slides
  with 30 objects each (6,000 objects, 200 of them bound): 1.7 ms of the 4.7 ms a command takes. A reverse index
  (placeholder → bound objects) is the answer if decks grow by a factor of ten; it is on the backlog as tech debt, not built.

**Why not derive the place on every read.** Every reader would need the layout, and a slide handed to another program or
another deck would lose where its objects are. **Why not refuse in a command that changes a placeholder** instead of
repairing: a Batch, an undo and a colleague's edit meet halfway through, and a refusal there loses work.
