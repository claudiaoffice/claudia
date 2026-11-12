---
id: D401
title: "OpenDocument import and export share one package, `claudia-odf-io`, built on lxml and byte splicing rather than on odfdo"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D401 · OpenDocument import and export share one package, `claudia-odf-io`, built on lxml and byte splicing rather than on odfdo

**The three apps' OpenDocument converters (odt now, then odp and ods) share one new package, `claudia-odf-io`, built on lxml and a byte-splicing layer; odfdo is not a dependency.** The package holds what no app owns alone: `names` (how ODF encodes style names, `NS`), `splice` (`XmlPart`: edit one XML part by recording edits against elements and splicing the new bytes into the original), `paragraph` (the text of one paragraph, changed in place; change marks put between characters), `package` (a package from its parts with its manifest, and `problems()` to check that a file is one) and `report` (`Loss`, `LossLog`, D405). The app packages (`claudia-composes-io` today) keep only what is about their own model.

**Notes.** The plan this replaces assumed "the same structure as for Microsoft Office", with odfdo as the library, the way python-docx, python-pptx and openpyxl are the libraries of D217, D219 and D220. Three reasons against odfdo, found in a spike on LibreOffice-written files: it parses a part and writes the tree back, and a tree writer changes bytes nobody edited (`&apos;` becomes `'`, the quotes of the XML declaration change), which makes D403's promise impossible; its high-level objects are per document type, where the shared layer needs only the splice and the paragraph engine; and it would be one more dependency for something that is a few hundred lines on lxml, which python-docx, python-pptx and openpyxl bring in already. odfpy was looked at for its grammar tables only (what may be inside `office:change-info`). This was a call made while implementing, not one the owner was asked about: if odfdo should come back, only `splice.py` and `paragraph.py` are affected. D70 (OpenDocument first) stands; its note "no import or export code exists" is out of date since docx (D217) and this.
