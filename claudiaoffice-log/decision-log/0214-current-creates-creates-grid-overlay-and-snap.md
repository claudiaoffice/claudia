---
id: D214
title: "A grid overlay in creates (E10.15, a new story — not previously in the backlog), and snapping to it, are two independent things"
status: current
applies-to: creates
date: 2026-11-07
round: "Restore with consent, and the line picker (twenty-sixth round)"
supersedes: []
superseded-by: []
previous-id: D151
---

# D214 · A grid overlay in creates (E10.15, a new story — not previously in the backlog), and snapping to it, are two independent things

**A grid overlay in creates (E10.15, a new story — not previously in the backlog), and snapping to it, are two independent things.** Whether the grid lines are *shown* is a client-local view preference (`lib/grid.ts`'s `useGrid`, localStorage, like Dark mode): not document state, never sent to the server, never undoable. Whether an object *snaps* is real, persisted document state — `SlideObject.snap` (default `true`), changed by its own command (`SetSnap`) with its own history entry — so an object keeps snapping even while a colleague has the lines hidden, until it is itself released. Default: the grid is shown and every object snaps, at 50 slide units; released from the object's own context menu, a swapping label ("Snap to grid" / "Release from grid") like "Undo <label>" already does, rather than a new checkbox `ContextMenu.vue` cannot yet draw. Dragging a corner with a fixed aspect (a circle, an image) snaps the dominant dimension only and derives the other from the aspect exactly, so snapping never throws the proportions off.

**Notes.** Owner's request, with a mock-up agreed first (`notes/mockups/grid-and-snap.svg`) and four open points settled by `AskUserQuestion`, each against its own recommended default: snap state persists in the document with a history entry (over a client-only guess); snapping applies to both move and resize (over move only); 50-unit default spacing (over 25 or 100); the context-menu item swaps its label (over a checkbox). Built on `grid-in-creates` as the branch stood at `886f484`, not rebased onto `main`'s later work. `AddObject.schema` 2→3, `SlideModel.state_schema` 3→4 (`claudia_creates` 0.3.0, `claudia_server` 0.16.0 for the new `set_snap` method); no keyboard shortcut yet (menu only, consistent with `view.panel`/`view.dark`) — left open for whoever picks this up next.

*Renumbered on 2026-11-10 from D151, a number that had been allocated twice by branches written in parallel (see `_rounds.md`, "One file per decision").*
