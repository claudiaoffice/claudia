---
id: D1536
title: "A provisional layout that nobody follows and nobody named is not shown, and is dropped when the deck is written as a template"
status: undecided
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1536 · Provisional layouts nobody follows are hidden, not deleted

The owner agreed that unnamed unused layouts "are removed automatically". A removal that happens in `settle` is not a
step in the log, so undoing the step that made the layout unused would have to bring a layout back that is gone. The
model therefore keeps it, and the clients leave it out of every list (it has `to_name` and no slide follows it);
writing the deck as a template drops it. **Open:** the owner may prefer the removal to be part of the command that makes
it unused (undoable, but every such command grows). Until then the layout list of a deck can hold such layouts, and
their names and ids count as taken.
