---
id: D1317
title: "Name & describe… is one dialog for every thing, and every thing can have a description"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1317 · Name & describe… is one dialog for every thing, and every thing can have a description

**Decided 2026-11-19** by the owner, answering question 4 of `specs/objects/names.review.md` (the proposal was a name only for a paragraph, list, table or range; the owner said no).

**Everything that has a name can also be described**: a picture, a chart, a shape, a text box, a slide, a sheet, a chart tab and, in composes, a paragraph, a list, a table; in computes a named range. *Edit ▸ Name & describe…* and the same entry in the right-click menu open **one dialog with a name field and a description field** for all of them, in all three apps (D1304, D1225).

**Why, in the owner's words:** the description is re-used for the **corkboard** feature (E16.5), where things carry a note. **When the corkboard is built the data structure is revisited**: "description" may have to split into a *description for blind users* (the alternative text of BITV 1.1.1, which today's `DescribeObject` is) and a *description as in a note the user jotted down*. Until then there is one field.

**Assumptions, for the owner to correct** (they are not in the answer):

* **Decorative** (the tick that says "this picture needs no alternative text") stays only for things that are drawn: pictures, charts, shapes, rendered text and text boxes. A paragraph or a range cannot be "decorative".
* ~~A paragraph's description does not change how the text is exported.~~ **Corrected by the owner (2026-11-19, D1318):** it is offered as a comment on export to Word and OpenDocument.
* ~~How a description of a paragraph, list, table or range is stored is not decided here.~~ **Decided in D1318:** the same way as the description of any other object.

**Notes.** Replaces the "name only" default of D1311's first proposal. The dialog without a name field is the bug of size 2 in the names review (N1); this decision says what the dialog is, not only that the field is missing.
