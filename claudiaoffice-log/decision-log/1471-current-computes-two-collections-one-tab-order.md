---
id: D1471
title: "Computes has sheets and slides as two collections and one tab order; it reads cell and slide anchors; an object may change holder from a sheet to a slide only"
status: current
applies-to: computes
date: 2026-11-22
round: "E6.31 Slides in computes (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1471 · Two collections, one tab order

`WorkbookModel` keeps `sheets` (id → `Sheet`) and `slides` (`Slides`, D1470) as what a sheet and a slide are, and
`tabs: list[Tab(kind, id)]` as the **only** order: every sheet and every slide in it exactly once, kept so by
`add_sheet`, `remove_sheet`, `add_slide` and `remove_slide` and nowhere else. `Tab.kind` says which collection an id
is in. The model becomes `ObjectModel[CellAnchor | SlideAnchor]`: `anchor_from_data` reads by `kind`, `check_anchor`
wants a cell anchor on a sheet and a slide anchor on a slide, `holders()` follows `tabs`.

The core's flag `objects_change_holder` becomes a hook, `may_change_holder(old, new)`, whose default is the flag's
behaviour; computes allows a sheet → slide move only, so "Move to Slide" is the existing `MoveObject` (D1351) and an
object cannot be moved from one sheet to another by the way.

The chart tab (`charts`, `Chart`, `AddChart`, `RemoveChart`) goes in the step that brings its stand-in (E6.31 step 3).
Nothing reorders a tab yet (as nothing reorders a sheet today); deleting a tab by hand is UX-68.

**Why.** The owner asked why the model would have sheets, slides and tabs (2026-11-22): a tab *is* a sheet or a slide,
so `tabs` holds references into the two collections and nothing else.

Architecture A3′, A4, A10 in `notes/e6-31-slides-in-computes.md`.
