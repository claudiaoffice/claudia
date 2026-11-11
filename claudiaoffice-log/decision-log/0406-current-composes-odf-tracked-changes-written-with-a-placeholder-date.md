---
id: D406
title: "An open suggestion is written to odt as a tracked change in the standard form, dated with a placeholder, because LibreOffice drops one without a date"
status: current
applies-to: composes
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D406 · An open suggestion is written to odt as a tracked change in the standard form, dated with a placeholder, because LibreOffice drops one without a date

**A suggestion with a replacement becomes a `text:changed-region` with a `text:deletion` (the deleted text inside it, a `text:change` mark in the paragraph) and a `text:insertion` (`text:change-start` and `text:change-end` around the new text), with `dc:creator` the suggestion's author ("Claudia AI" if none) and `dc:date` 1970-01-01T00:00:00.** The paragraph's own text then reads as the replacement; the deleted word is kept in the change. Ids are `ct1`, `ct2`... and skip the ones a file already has. `export_office` writes them only when asked (D411; off by default, D212).

**Notes.** Verified against LibreOffice 24.2.7 by converting to docx: with a date the change comes out as `w:del` and `w:ins`; with no `dc:date` both words stay in the text as plain text and no change exists. D147 refused to invent timestamps for docx, where Word does not need one; here the epoch is the placeholder LibreOffice itself writes for a change that came from a file without a date, and it keeps the output deterministic like the zip timestamps of D404. A reviewer sees an old date on the change when the converter is given no time for it: the model has none (D147). `export_office` does give one, from the log (D411).
