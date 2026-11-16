---
id: D680
title: "A model-driven AI reads and writes a text through a document lens"
status: current
applies-to: composes
date: 2026-11-16
round: "The AI in composes (E7.10)"
supersedes: []
superseded-by: []
---

# D680 · A model-driven AI reads and writes a text through a document lens

**Composes gets the same model-driven AI as computes and creates: a document lens (`DocumentLens`) beside `WorkbookLens` and `SlideLens`, and the same read-act-correct loop (`ModelEngine`).** A server with a language model answers `@ai` in a text with the model, which is told how the text is built (the paragraph styles, the headings, the start of the text, the paragraph the asker's cursor is in), may read paragraphs, the outline, the styles and the open suggestions, and gets every change reported back as the touched paragraphs as they now are. What it may write is D640's: in *act* the words and the paragraph styles, in *suggest* only suggestions; through the methods of D681, and in *act* it may also add paragraphs (`add_paragraphs`). Without a language model the scripted stand-in (`TextEngine`) answers, as D640 describes.

**Notes.** The owner's request of 2026-11-16: the AI in composes was still a stand-in; build the infrastructure as for computes and creates ("a DocumentLens the same way there is a WorkbookLens"). D640 (2026-11-15) had already opened composes' writes to the AI through its allow-list, but there was no lens, so `model_assistant_for` returned `None` for a text and a server with `--ai` answered with the stand-in. `Lens.orient` now takes `asker` (who asked) and `writes` (the write methods offered to the model for her), so a lens can say where she works and give an example of a method she allows; the workbook and slide lenses ignore both for now. Still open, as for the other apps: one answer as one undo unit, "ai, on behalf of X" in the history, what the asker has selected as context (E7.5).
