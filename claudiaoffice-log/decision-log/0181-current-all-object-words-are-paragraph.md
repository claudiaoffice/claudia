---
id: D181
title: "An object's words are a paragraph, the same entity composes uses, and an object therefore has two styles"
status: current
applies-to: all
date: 2026-11-08
round: "PNG, and an object's words as a paragraph (thirty-second round)"
supersedes: []
superseded-by: []
---

# D181 · An object's words are a paragraph, the same entity composes uses, and an object therefore has two styles

**An object's words are a paragraph, the same entity composes uses, and an object therefore has two styles.** `claudia_core.paragraphs` holds `Paragraph` (id, style, text, runs) and `Run` with the run arithmetic that was `claudia_composes.runs`. `ObjectBody.text: str` becomes `ObjectBody.paragraph: Paragraph | None` — a text box always has one, a shape may, an image never. So a shape's label now carries a paragraph style, an alignment and per-author runs exactly as a paragraph of a document does. The consequence worth stating out loud: an object has **two** styles, and they mean different things. The object's own (`body.style`) says what the box looks like — `fill`, `stroke`, `stroke-width` (D178); its paragraph's (`body.paragraph.style`) says what the words look like. Both are entries in the one `StyleBook`, so the same core style commands change either. A new object's paragraph starts under the object's own style (`paragraph_for`), so nothing looks different until somebody points it elsewhere, and pointing it elsewhere is a deliberate act rather than a migration. New commands: `core.SetParagraphStyle`, and `core.SetParagraph`, which sets a whole paragraph at once. composes' `Block` becomes an alias of `Paragraph`; its model replaces paragraphs in its list rather than editing them in place.

**Notes.** The owner's request, and the move this chat identified two rounds ago as the one that would let a shape carry real text. **A paragraph is immutable, and that is the point, not ceremony:** every command builds its own inverse from the state it found, so a paragraph edited in place would hand the inverse the new text. Exercising it end to end caught exactly that bug in a form the tests had not: `SetText`'s inverse carried only the characters, so undoing a colleague's edit restored the right words but re-attributed them to whoever pressed undo. `core.SetParagraph` exists to be that exact inverse, runs included. `test_purity.py`'s `APP_WORDS` lost "paragraph": the guard keeps the kernel from learning one app's shape, and a paragraph stopped being composes' idea the moment a creates text box and a label on a sheet carried the same one. "slide", "sheet", "cell", "workbook" and "formula" all stay guarded.
