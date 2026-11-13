---
id: D293
title: "Every slide has speaker notes, written in Markdown, stored in the document"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D293 · Every slide has speaker notes, written in Markdown, stored in the document

**Every slide may carry speaker notes, and the notes are Markdown.** The field is in the document, so setting it is a command: undoable, attributed like any edit, visible in the history, and writable by the AI as a suggestion (D262, D265). The notes are shown formatted in the presenter view and nowhere else: never on the slide, never on a slide page of the print (D917).

**Notes.** The owner's answer to question 2, 2026-11-13: "notes in the model should be able to handle Markdown". Which Markdown, and how the notes pass through ODP and PPTX, is proposed in D298 and `undecided`. State schema 8 of `SlideModel` (with D294).
