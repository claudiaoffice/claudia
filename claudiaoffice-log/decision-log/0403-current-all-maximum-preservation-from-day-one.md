---
id: D403
title: "OpenDocument gets maximum preservation from day one: import, export and edit-and-reexport, and a byte outside the edit is the original's"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D403 · OpenDocument gets maximum preservation from day one: import, export and edit-and-reexport, and a byte outside the edit is the original's

**For the OpenDocument formats the promise of D217 is kept from the first version, and stronger: an edited file is the file it was, with only the edited elements changed.** There are three paths for each format, not one: a file can be read (and what the model does not show is listed), a model can be written as a new file (and what the file cannot hold is listed), and an *edited import* is exported by patching the original. In `content.xml` every byte outside the paragraphs (later: cells, slides) that were edited is the original's, and every other part of the package has the same content as before. The owner's decision, 2026-11-11, on the alternative of regenerating the file and listing what is lost.

**Notes.** D217's whole-part `reconcile` cannot carry this: an odt keeps every paragraph, every sheet and every slide in one `content.xml`, so there is no untouched part to restore. `XmlPart` (D401) finds elements by parsing and edits by splicing bytes at their spans, so nothing is re-serialised. The in-paragraph engine edits the characters that differ (a token-level diff refined by common prefix and suffix) and leaves the elements where they were; it was checked against 32,000 random paragraphs and by a 150-case property test of `apply_edits_to_odt`, and the results were opened in LibreOffice 24.2. What does not hold: the zip container is written again (the parts' contents are the same, the zip's bytes need not be), and `meta.xml` is not updated (the file does not say Claudia edited it).
