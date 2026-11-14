---
id: D375
title: "Importing pptx or odp: masters that are the same design are proposed as one template; unused layouts stay in the file only"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Real-world documents: templates and layouts in creates (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D375 · Importing pptx or odp: masters that are the same design are proposed as one template; unused layouts stay in the file only

**Proposal.** On import, slide masters (pptx) or master pages (odp) whose theme colours, fonts, background and
placeholder frames and text styles are equal — ids and names left out — are proposed as one template; a master that
differs is kept as its own template or, if the person chooses, made a named variant. Nothing is merged without the
person's yes (the templates step of the import screen). Layouts no slide uses are not brought into the model; they stay
in the file, which an edit keeps (D219). Placeholders map to slots by type (`title`/`ctrTitle` → title, `body`, `obj`
or none → text, `pic` → picture), `dt`/`ftr`/`sldNum` to running items, a slide's placeholder shape to that slot's
content with its inherited formatting resolved.

**Notes.** Found on a real deck the owner supplied (kept out of the repository): 14 masters, one layout each, the same
theme fourteen times, from slides pasted with "Keep source formatting"; its placeholders held all of its text, so it
imported empty. Screen G in `claudiaoffice-log/notes/mockups/creates-templates-import-and-new.svg`.
