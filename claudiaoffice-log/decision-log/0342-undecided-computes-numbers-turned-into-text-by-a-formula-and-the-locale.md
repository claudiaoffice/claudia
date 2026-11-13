---
id: D342
title: "Open: does a formula that turns a number into text (CONCAT, &, TEXT without a format) follow the person's locale, as Excel does?"
status: undecided
applies-to: computes
date: 2026-11-13
round: "Real-world documents: xlsx as Excel writes it today (branch real-world-docs)"
supersedes: []
superseded-by: []
---

# D342 · Open: numbers turned into text by a formula, and the locale

**Excel turns a number into text with the decimal separator of the computer it runs on: `="Rate "&0.0495` is
`Rate 0,0495` in German Excel and `Rate 0.0495` in English Excel. The model always writes `0.0495`.** On the real
workbook of D340 this is the one formula of 47,290 whose value differs from Excel's.

The two ways:

1. **As today: a document computes the same everywhere** (D910 for the layout says the same of pages). A model shared
   between a German and an English user shows the same text to both; a German user sees a point where Excel shows a
   comma.
2. **As Excel: by the locale of the person who looks.** Then a computed text differs between two readers of the same
   document, and a formula that compares such a text with a typed one gives different answers to them.

**Notes.** A third way is a document's own language setting (composes has one, D915): the text of a formula follows
the document's language, not the reader's, so the document still computes the same everywhere and a German workbook
looks German. Named number formats (E6.14) decide how a number *shown in a cell* looks, which is a separate question;
this one is about text a formula *computes*. Not blocking: the file keeps Excel's text for such a cell as long as nobody edits it
(D341); only the model shows the point.
