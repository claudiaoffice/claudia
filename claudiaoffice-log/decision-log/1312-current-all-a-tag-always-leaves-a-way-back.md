---
id: D1312
title: "A tag that moves the view always leaves a way back, also inside one text, sheet or slide"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1312 · A tag that moves the view always leaves a way back, also inside one text, sheet or slide

**Decided 2026-11-19** by the owner (E1.13: "yes, let's have the way back mechanism").

D551 gave a tag a **Back chip**, "← Back where I was", but only when the tag takes the view to **another container** (a slide, a sheet, a chart tab). Inside one container there is no chip: a tag to a paragraph far down a text, or to a cell far from the one being worked on, moves the view and leaves nothing to come back with, which D554 listed as not built. **From now on every tag jump that moves the view leaves the way back**, in all three apps: what it remembers is *where the view was* (container and the place in it), not only which container.

**Notes.** What the owner has not yet been asked, with defaults, is in `specs/objects/names.review.md` (how long the chip stays, a menu entry for when the History & Chat panel is folded away, the key). The existing chip is shown in `notes/mockups/dock-05-reference-tag-jump.svg`; no new mock is proposed unless the owner wants one.
