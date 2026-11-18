---
id: D226
title: "Deleting a style never changes how anything looks and never leaves a dangling reference"
status: current
applies-to: all
date: 2026-11-17
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D226 · Deleting a style never changes how anything looks and never leaves a dangling reference

**Decided 2026-11-17** (the owner took the proposal and the recommendations of that day: "go with your recommendations"). Before: an open question carried over from the decision log's "Open design questions" on 2026-11-10.

**Deleting a style never changes how anything looks and never leaves a dangling reference.** The person chooses how:

- **Keep their look.** What is based on the style moves up under the style's own parent; whatever has the style itself moves to a *stand-in* (D781).
- **Re-base on another style.** The same, under a style of the same kind that the person names (never the style itself, nor one based on it). Everything that moves *says what differs* from its new parent so that its look is held (D781).

Root, built-in and template styles cannot be deleted, only hidden (D780). *Where the dialog appears is settled by D302.* Row heights and column widths are sheet layout, not style (D135).

The whole deletion is **one logged step, undone as one** and per author (D782).
