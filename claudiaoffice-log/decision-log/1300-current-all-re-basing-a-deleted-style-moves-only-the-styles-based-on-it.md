---
id: D1300
title: "Re-basing a deleted style moves only the styles based on it; what has the style itself goes to the stand-in"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1300 · Re-basing a deleted style moves only the styles based on it; what has the style itself goes to the stand-in

**Decided 2026-11-19** by the owner (taking the proposal). Settles the open point of E1.10 about D785's *Re-base on another style*.

**Re-base re-parents only the styles that were based on the deleted style.** Whatever has the deleted style itself (a paragraph, an object or its words, a range of cells) does not move to the named style: it moves to the stand-in `<name> (kept)` under it (D781). So a re-base never makes a style a parent of something that had no relation to the deleted one, and every look is held.

**Notes.** This is how `plan_delete_style` already works; the decision closes the question so the screens (D783) and the tests can rely on it, and so nobody extends *re-base* to "everything that pointed at the style" later. *Assign another style* (D785) stays the way that moves everything.
