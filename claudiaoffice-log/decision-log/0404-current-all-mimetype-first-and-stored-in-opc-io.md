---
id: D404
title: "The `mimetype` rule of an OpenDocument package lives in `claudia-opc-io`'s `write_parts`, and every part gets the same timestamp"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D404 · The `mimetype` rule of an OpenDocument package lives in `claudia-opc-io`'s `write_parts`, and every part gets the same timestamp

**`write_parts` writes a part called `mimetype` first and stored (not compressed), with no extra field, and gives every part the timestamp 1980-01-01; a package without that part is written as before.** ODF 1.3 part 3, 3.3 asks for this so that `file`, browsers and upload filters can read the type of a document at a fixed place without unzipping. LibreOffice does not mind either way, which is why it would have gone unnoticed. `claudia-opc-io` becomes 0.2.0.

**Notes.** It is a rule of the zip, not of any format's content, so it is in the package that moves between a zip and a dict of parts (D217), not in `claudia-odf-io`. The fixed timestamp also makes the OOXML files deterministic: the same parts always give the same bytes. The contents of the parts are unchanged for docx, pptx and xlsx, so D217, D219 and D220 are not touched.
