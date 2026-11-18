---
id: D226
title: "Deleting a style never leaves a dangling reference, and never changes a look unless the person goes back to no style"
status: current
applies-to: all
date: 2026-11-17
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D226 · Deleting a style never leaves a dangling reference, and never changes a look unless the person goes back to no style

**Amended 2026-11-18 by D784, then D785** (assigning another style, which is the default as in other office software; *keep their look* is gone). **Decided 2026-11-17** (the owner took the proposal and the recommendations of that day: "go with your recommendations"). Before: an open question carried over from the decision log's "Open design questions" on 2026-11-10.

**Deleting a style never leaves a dangling reference, and — except where the person assigns another style (D785) — never changes how anything looks.** The person chooses how, in this order (D785):

- **Assign another style.** What has the style, and what is based on it, goes to a style of the same kind that the person names (the plain style of the kind is offered first). Looks change, and the dialog says how many first.
- **Re-base on another style.** What is based on the style moves under a style of the same kind that the person names, never the style itself nor one based on it, and *says what differs* from its new parent so that its look is held; whatever has the style itself moves to a *stand-in* (D781).

Root, built-in and template styles cannot be deleted, only hidden (D780). *Where the dialog appears is settled by D302.* Row heights and column widths are sheet layout, not style (D135).

The whole deletion is **one logged step, undone as one** and per author (D782).
