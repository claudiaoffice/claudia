---
id: D409
title: "OpenDocument output is checked against LibreOffice as well as against itself"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D409 · OpenDocument output is checked against LibreOffice as well as against itself

**Beyond the unit tests and `problems()` (zip rules, manifest agreement, well-formed XML, `office:version`), OpenDocument output is opened in LibreOffice: a separate Linux CI job (`odf-libreoffice`, `continue-on-error`, so not blocking at first) runs `scripts/odf_libreoffice_check.py`, which converts every odt fixture, the edit each case makes and a file made from a model with `soffice`, and checks that every word of every block is in the text that comes out, in order; schema validation against the OASIS RelaxNG schema is added when the schema can be fetched.** The owner agreed on 2026-11-11. The script exits 0 where `soffice` is missing and says it skipped. **Not yet done:** making the job blocking (when it has a track record), and the schema.

**Notes.** The OASIS schema was not reachable from the development sandbox (the proxy refused the connection), so the rules the structural check applies come from the specification text and odfpy's grammar tables. The check compares words, not exact text, because LibreOffice's own text export prints a footnote's number inside the sentence and runs a tracked deletion and its insertion together. Three of the six odt test documents are files LibreOffice wrote, so the reader is tested against the reference implementation's own layout, not only against files made by this code.
