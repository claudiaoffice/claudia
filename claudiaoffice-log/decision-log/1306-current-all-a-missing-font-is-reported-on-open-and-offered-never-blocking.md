---
id: D1306
title: "A missing font is reported when a document opens and offered from the font service; it never blocks opening"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1306 · A missing font is reported when a document opens and offered from the font service; it never blocks opening

**Decided 2026-11-19** by the owner (taking the proposal; E1.9).

When a document is opened, the server checks its manifest (D26, D38) against what it has, **including the fonts the font service can provide** (`providable_fonts`, D905, D1041). A font the server lacks but can fetch is **reported with a one-click offer to get it**; one it cannot is reported with the stand-in that will be shown. Nothing here stops the document from opening or being edited (`RequirementReport.ok` already says so). The report is the "list of fonts and their substitutes" of the font stance of 2026-11-16: an imported font name is kept, and the stand-in is made clear.

**Notes.** The check is not wired today: the server never calls `environment_of` with `providable_fonts`. The words and screens go with the font round (E3.13, D1041); this decision only says when the check runs and that it never blocks. The function half of the manifest (a missing or changed UserFunction) is not decided here.
