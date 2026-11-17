---
id: D1061
title: "Text flows around a floating object in four modes: over, around, above and below, behind"
status: current
applies-to: composes
date: 2026-11-17
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1061 · Text flows around a floating object in four modes: over, around, above and below, behind

**An object in composes has a wrap, one of *over the text*, *around*, *above and below* and *behind the text*, kept in the anchor beside `dx`/`dy` with a distance in pixels.** A document without the field means *over the text*, so no existing document changes.

**The default for a new object is *above and below*** (the owner, 2026-11-17, asked for "text above and below the object as default mode"). Read as: every object put in by the person (picture, container, text box, shape); objects that come in from DOCX or ODF keep the wrap the file says.

**Notes.** Mock-up `notes/mockups/composes-object-wrap.svg`, rules and format mapping in `notes/composes-floating-object-layer.md`. Proposed, not yet confirmed by the owner: because the editor does not show wrap until D1062's second stage, the default for new objects is switched on only when the editor draws it, so that what the person sees is what prints; until then the print and the print preview wrap and the editor does not.
