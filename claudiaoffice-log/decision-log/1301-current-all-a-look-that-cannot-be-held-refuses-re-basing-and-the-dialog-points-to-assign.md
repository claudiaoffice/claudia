---
id: D1301
title: "A look that cannot be held refuses re-basing, and the dialog points to assigning another style"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1301 · A look that cannot be held refuses re-basing, and the dialog points to assigning another style

**Decided 2026-11-19** by the owner (taking the proposal). Settles the second open point of E1.10.

D781 refuses a re-base when the deleted style sets a property that has no neutral value, the same in every app (`font-family`, `font-size`, `color`, `text-align`, `hyphens`, `vertical-align`, and a shape's `fill`, `stroke`, `stroke-width`). **The refusal stays.** No "neutral" value is invented for those properties: a made-up value would change a look silently, which is what D226 forbids.

**The dialog helps instead of only refusing.** Where *Re-base on another style* is not offered, the reason is given in words (which property) and *Assign another style* is the way offered (D785), with the count of places that will look different. A target that cannot hold the look is shown disabled with the reason, as D781 already says.

**Notes.** Considered and not chosen: a neutral value per property taken from the plain style of the kind (it would hold the look only until the plain style changes), and a third way to delete (D784 had three and the owner removed one).
