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

**Details, decided 2026-11-19** by the owner (answers 8 to 10 of `specs/objects/names.review.md`, all as proposed):

* **What Back restores:** the position of the view, that is the container and the top visible place in it (paragraph, row and column, slide). A tag jump never moves the caret or the selection, so there is nothing else to give back.
* **How long the chip stays:** until it is used, or until the person types or clicks into the document, or jumps again. Not three seconds.
* **A menu entry for the folded-away dock: View ▸ Back where I was**, in all three apps. The owner asked for "some combo with B": **Ctrl+Shift+B** (Cmd+Shift+B on a Mac). It is free in all three apps (Ctrl+Alt+B is Text Box, Ctrl+Shift+Alt+B is Number Headings), and it is Back's own letter. **Assumption, to be checked in the build:** Chrome and Firefox use Ctrl+Shift+B for the bookmarks bar; a page may take the key, but this has to be tried in both browsers before the manifest is changed.
* Screens: `notes/mockups/names-04-way-back.svg`, `names-05-way-back-menu.svg` (the existing chip is in `dock-05-reference-tag-jump.svg`).
