---
id: D450
title: "Search in composes and creates looks in everything that has words, switched by kind"
status: current
applies-to: all
date: 2026-11-14
round: "Search & replace in composes and creates (branch `search`)"
supersedes: []
superseded-by: []
---

# D450 · Search in composes and creates looks in everything that has words, switched by kind

**What is searched.** The owner's answer (2026-11-14) to the proposal for E9.28 and E10.19: *search all objects and texts, including speaker notes*. So the panel of D282 is the same in the three apps and the app says what it can look in, as switches (the host's `switches`, all on by default):

* **composes:** Text (body paragraphs), Headings (heading 1, heading 2 and title styles), Remarks (the remark style), Objects (the words of text boxes and shape labels that float over the text) and Descriptions (the alt texts of objects). The kind of a paragraph is read from its style chain, so a heading is a heading however a document names its style.
* **creates:** Text (words in text boxes), Shape labels, Speaker notes and Descriptions (alt texts).
* **computes:** unchanged (Text, Formulas, Values; D285).

**Scopes.** Composes: the whole text, this section (from the heading of level 1 or 2 the caret is in to the next one of the same or higher rank) and the selection (a partly selected first or last paragraph is searched from or up to the selection's edge). Creates: all slides or this slide (the owner: "this slide / all slides is perfect").

**Places.** As D289: composes `{block}` (with `offset` when only part of a paragraph is searched) or `{block, object, source}`; creates `{slide, object, source}` (`source` is `box`, `label` or `description`) or `{slide, source: "notes"}`. A match in an object of a text is shown by taking the person to the paragraph the object hangs from; the editor does not draw objects. Creates draws the match in the words of the object on the slide and, for a match in notes, shows the notes under the slide.

**Replace.** Like D286: the replacement is made of the commands a person would have made (composes: `DeleteText` and `InsertText` per match, applied from the end of the paragraph so the authorship of the text around it stays and the person replacing is the author of the new words; creates: `SetParagraph` and `DescribeObject` for objects, `SetSlideNotes` for notes), as one `Batch` and one Undo step. Nothing of a search is stored in a document, so there is nothing to add to the Office or OpenDocument import and export.

**Not searched yet.** Footnotes, citations and fields (composes), chart titles, slide names and layout placeholders' prompt text (creates), because they do not exist or have no editable words yet (D287 (4)).

**Notes.** Built 2026-11-14 on branch `search`: `claudia_composes.search`, `claudia_creates.search`, the app-neutral `claudia_server.search_methods`, `web/app/lib/text-search-host.ts` and `slide-search-host.ts`. The words "Whole cell", "a cell" and the like in the panel come from the host (`unit`: `cell` or `text`).
