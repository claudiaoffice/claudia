---
id: D1303
title: "Names of things come from the file on import and go back into it on export; what a format cannot carry is reported"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1303 · Names of things come from the file on import and go back into it on export; what a format cannot carry is reported

**Decided 2026-11-19** by the owner (taking the proposal; E1.13).

**Import.** A slide, sheet, chart tab or object takes the name the file gives it (pptx, odp, docx, odt, xlsx, ods). Where two names are the same cleaned and case-folded (D550), the later ones get a numeric suffix (`Figure 1`, `Figure 1 (2)`), in the document's one namespace. A thing the file does not name gets a generic name (D1305).

**Export.** Every format writes the names it has a place for. What a format cannot carry (today object names in pptx and odp) is **named in the loss report** the way slide names already are (`names`), never dropped silently.

**Notes.** This closes the "names in imports and exports" and "object names are not written to pptx and odp and their loss is not reported" items of E1.13.
