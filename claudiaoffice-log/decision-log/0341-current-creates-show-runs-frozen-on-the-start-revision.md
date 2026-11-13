---
id: D341
title: "The show runs frozen on the revision it started from; later changes are offered between slides, never applied by themselves"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D341 · The show runs frozen on the revision it started from; later changes are offered between slides, never applied by themselves

**The show runs on the revision at its start.** Edits made by others during the talk do not reach the audience. The presenter view says "N changes since you started" and offers to update between slides; nothing changes on its own, which is D72's rule for material that moves between documents, applied to a show.

**Notes.** The owner's answer to question 3, 2026-11-13 ("yes, frozen during presentation"). The frozen view is the same non-destructive local preview that the history uses for a past checkpoint, so it needs no new kind of document state. Open: what "update" does to the slide the presenter is on; proposed in `notes/e10-2-presenter-mode.md` as: it takes effect on the next slide change.
