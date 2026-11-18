---
id: D1203
title: "A cell is one paragraph, and a number in it is words that are read as a number when something needs the value"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1203 · A cell is one paragraph, and a number in it is words that are read as a number when something needs the value

**A table cell holds exactly one `Paragraph` (D181): its words, its runs (who wrote what), its fields and its style. Enter inside a cell starts a new line in it, not a new paragraph.** Several paragraphs, lists or pictures in a cell are a later decision.

**What is typed is what is stored and exported.** A total, a sort or a chart reads the value of a cell with the document's language (`SetLanguage`, D915), not the client's locale, so every client agrees: `1.234,5` is 1234.5 in a German text and 1.2345 in an English one. A column of numbers is aligned on its decimal separator by the layout. Nothing reformats a number unless a person asks (a column command, undoable). Computes' number formats (D378) stay computes': they would hide what a docx or odt contains.

**Notes.** The cell's paragraph id is `<table id>/<row id>/<column id>` (D1210). Confirmed 2026-11-18 ("cell content: one paragraph", "numbers: as text").
