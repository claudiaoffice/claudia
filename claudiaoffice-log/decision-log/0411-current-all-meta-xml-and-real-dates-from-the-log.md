---
id: D411
title: "`meta.xml` says who made a document and when, from the log; a tracked change is dated with when it was proposed; `export_office` writes tracked changes when asked"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D411 · `meta.xml` says who made a document and when, from the log; a tracked change is dated with when it was proposed; `export_office` writes tracked changes when asked

**Claudia knows when a document was made and last changed and by whom (the container's dates and every log entry's server time and author), so an OpenDocument file says so in `meta.xml`, and a tracked change says when its suggestion was proposed.** `claudia_odf_io.new_meta` writes the part of a new file; `update_meta` and `update_package_meta` change an imported file's by splicing (D401): `dc:creator` and `dc:date` become the last change `meta:editing-cycles` goes up by one and the generator becomes `Claudia`, while the statistics, the keywords and the user-defined properties the file came with stay as they were; a file without `meta.xml` gets one (and a manifest entry). `meta:initial-creator` and `meta:creation-date` are written only when the file has none: who made a document does not change when somebody else edits it. Dates are UTC to the second with a `Z`. `claudia_composes_io.export_info(log, branch)` reads the log for the converters (`DocumentInfo`, and `{suggestion id: time}` from the entry that proposed each suggestion); a converter never reads a log. The same dates go to docx as `w:date` of a tracked change. An unknown date stays the placeholder of D406 (odt) or is left out (docx, D147).

**`export_office` takes `tracked_changes` (default off).** Off is the clean copy of D212; on, the open suggestions that propose a replacement are written as tracked changes (D406), dated and signed as above. The text app's Export dialog gets a checkbox for it; its screen design (`notes/mockups/export-dialog-tracked-changes.svg`) is to be agreed before the checkbox is built, as every screen is. **To keep the edit small, `XmlPart.set_attributes` changes the attributes of one start tag and leaves the rest of the element where it is** (a moved slide object, D412).

**Notes.** The metadata of a file that was not changed is not touched (an unchanged import comes back as the same bytes, D403). The title is not in the log, so `export_info` leaves it to the caller. docx's `docProps/core.xml` is not updated: Word recomputes it, and D217's preservation is of what the file has. D406's "placeholder" and D410's "does not write them" are as they were for an export that says nothing about tracked changes or for a document whose log is empty.
