---
id: D402
title: "`claudia-composes-io` reads and writes odt: a block is a paragraph of the flow, and an edit is patched onto the original bytes"
status: current
applies-to: composes
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D402 · `claudia-composes-io` reads and writes odt: a block is a paragraph of the flow, and an edit is patched onto the original bytes

**`text_to_odt`, `odt_to_text`, `apply_edits_to_odt`, `odt_import_losses` and `odt_export_losses` are the odt counterpart of the docx functions of D217.** A block of the model is every `text:p` and `text:h` in the flow of the text, also those in lists and sections, but not the paragraphs in table cells; its id is its place in that order (`b1`, `b2`...), so a baseline and its file agree without the file carrying ids. `apply_edits_to_odt(original, baseline, current)` patches the original bytes: a changed text is edited in place (spans, links, bookmarks, notes, fields stay), a changed style turns a paragraph into a heading or back, a block added goes next to the paragraph before it (inside whatever holds that paragraph: a block added after a list item is a paragraph of that item, because the model has no bullets to give it), a block removed goes with what is inside it (each note, frame or comment is counted as `removed-<kind>` in the optional `losses`), open suggestions become tracked changes (D406). With nothing changed the result is the original bytes. **It raises `UnsupportedEdit`** for blocks moved relative to each other (a move would have to carry what is inside a paragraph, which the model does not know) and for a baseline that is not what the file holds.

**Notes.** An odt with no paragraph reads as a model with one empty block, which is what a new model is; that block is nothing to patch and, while empty, nothing to add. docx raises for adding or removing a paragraph; odt does not, because an element in `content.xml` can be added and removed without reconciling a whole part (D403). A new file gets a page (A4), the five styles of D407 and no automatic styles.
