---
id: D1066
title: "How the wrap is written to and read from ODF and DOCX"
status: current
applies-to: composes
date: 2026-11-18
round: "The floating object layer in composes (branch floating-objects)"
supersedes: []
superseded-by: []
---

# D1066 · How the wrap is written to and read from ODF and DOCX

**ODF: `style:wrap="none"` means *above and below*, not "nothing wraps"; *over* is `run-through` with `foreground`, *behind* is `run-through` with `background`, *around* is `parallel` with margins from the gap. DOCX: `wrapNone` (with `behindDoc` for *behind*), `wrapSquare` and `wrapTopAndBottom`, the gap as `distT/B/L/R` in EMU (9525 per pixel).** Both directions use the same table (`claudia_composes_io._wrap`), and an object whose file says nothing is read as *over*.

**Why.** The earlier ODT export wrote `wrap="none"` for every object, which LibreOffice reads as above and below: a bug (found 2026-11-18, fixed). A kept file's edit of the wrap goes into a derived graphic style with `style:parent-style-name`, so the other objects that share the style do not change.

**Not covered.** `dx`/`dy` is not written to the files yet (the offset of an object off its anchor character); an imported object lands at its anchor.
