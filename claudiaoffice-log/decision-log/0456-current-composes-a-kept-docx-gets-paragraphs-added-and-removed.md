---
id: D456
title: "The docx of a kept file has paragraphs added and removed in place, and says what goes with a removed one"
status: current
applies-to: composes
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D456 · The docx of a kept file has paragraphs added and removed in place, and says what goes with a removed one

**`apply_edits_to_docx` patches a block that was added or removed into the kept file, as `apply_edits_to_odt` does. Until now it refused (`UnsupportedEdit`), and the server wrote a new file that dropped the file's tables and pictures. A text edited in the commonest way (Enter, Delete, a pasted paragraph) therefore lost most of a Word file; now it keeps everything the text does not show.**

**Notes.**

* *Where a new paragraph goes.* Right after the paragraph of the block before it in the text; a block that comes first goes right before the paragraph of the next block that is in the file; a text with no other block in the file puts it last in the body. A table that follows the paragraph before stays behind the new paragraph: the model has no tables and cannot say on which side of one the author meant.
* *What goes with a removed paragraph.* The paragraph and its runs. What a paragraph holds that its text does not show (picture, footnote, endnote, comment, hyperlink, tracked change) is named as `removed-<kind>` in the `losses` that `apply_edits_to_docx` is given -- the names `apply_edits_to_odt` uses (D441). A paragraph that carries the properties of a section (`w:pPr/w:sectPr`) is only emptied, so that the two sections it separates do not become one; it comes back as an empty block when the file is read again.
* *Order.* Blocks cannot be moved relative to each other: the patch raises `UnsupportedEdit`, as the odt does, and the server writes a new file with `not-patched`. A baseline that is not what the file holds (another number of paragraphs) is refused the same way, where it used to fail on an index.
* *Styles and lists.* A new paragraph is written like a paragraph of a new file: its Word style (a style of the text that the file lacks is added to it first, D455) and its list item (D453). A style the text lacks is body text and a `style` loss.
* *Untouched paragraphs.* Every other paragraph, table and part of the package is exactly as it was.
* *The words of a paragraph that stays.* When the text of a paragraph is written again, only its runs of words are replaced; a run that holds a picture, the mark of a note or a field stays, and the new words follow it. (A hyperlink is not a run of its own: its words are still counted twice when the paragraph is edited; see the notes.)
