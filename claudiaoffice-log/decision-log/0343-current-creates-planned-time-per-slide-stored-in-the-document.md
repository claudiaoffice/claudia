---
id: D343
title: "A planned time per slide is stored in the document, and the total is always in view"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D343 · A planned time per slide is stored in the document, and the total is always in view

**A slide may carry a planned time, in whole seconds, and it is stored in the document** next to its notes (one command, undoable, attributed). It is simple to set: a chip beside the notes field, the key `T`, the slide's context menu; `m:ss` or minutes. The **total of the planned times is always in view**: at the foot of the slide rail, in the overview and in the presenter view, which also shows the time spent on the current slide and the whole talk against the plan. Nothing is enforced, and nobody has to plan.

**Notes.** The owner's wish of 2026-11-13: "simple to set a timer per slide (how much time do I want to spend on this), and see how long the whole thing is going to take", and, asked whether the times live in the document: "Yes, times are stored in document". Screen G of `notes/mockups/presenter-mode.svg`. The optional "available time" and the after-the-show list are proposals, D348. ODP and PPTX have no field for a planned time (PPTX's slide timings are automatic advance, a different thing): the times travel in Claudia's own format only, and the export dialog says so. Replaces the first draft's idea of a per-session planned duration.
