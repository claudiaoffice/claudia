---
id: D1535
title: "A layout that a slide follows cannot be removed, the basic layout cannot be removed at all, and two layouts never have the same name"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1535 · A layout in use cannot be removed

`RemoveLayout` refuses a layout a slide still follows and the basic layout; `delete_layout` (D1533) moves the slides
first. Names are compared without regard to case. Naming a provisional layout (`RenameLayout`) ends its waiting for a
name (`to_name`); undoing it brings the waiting back. The layouts are renamed, hidden and put in order (the first layout
that is not hidden is what a new first slide follows) by commands with their inverse.
