---
id: D1311
title: "Paragraph names: numbering after edits, the # list, headings, and what the Office formats carry"
status: undecided
applies-to: composes
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1311 · Paragraph names: numbering after edits, the # list, headings, and what the Office formats carry

**Proposed 2026-11-19, not yet confirmed by the owner.** Consequences of D1310 that the owner has not yet answered; each has a proposed default in `specs/objects/names.review.md`, where the owner can veto.

* **Numbering after edits.** A new paragraph gets the first free `Paragraph N` (D550), so a paragraph inserted between 3 and 4 is not "Paragraph 4"; names are stable and never renumbered (the id is the identity, D550).
* **Split and join.** A split keeps the name with the first part and names the second; a join keeps the surviving paragraph's name; undo gives both back.
* **The `#` list** (D551) shows what is in the writer's view, so generic paragraphs appear only for the paragraphs in sight, each as `Paragraph 12 · first words of the text`; everything a person renamed, and every heading, is always offered; typing filters across the whole document.
* **Headings.** The menus workbook (`claudia-menus.xlsx`, context menu *Section header*, which the owner agreed) says a heading's name **is its title**: Name & describe… on a heading is pre-filled with the section title and **locked**. That contradicts "every paragraph is called Paragraph N" for headings, so the proposal follows the workbook: a heading is named by its own words and is not renamed in the dialog (the title is edited in the text). **Open inside it:** two headings with the same title ("Introduction" in two chapters) would share one name in the one namespace (D550). Proposal: the second is shown as "Introduction (2)", like a name imported twice (D1303); the title in the text is not changed.
* **Docx and odt.** A bookmark that wraps one paragraph is read as its name on import (when it fits D550's rules); **export writes a bookmark only for a name a person gave**, not for generic ones, so that a 500-paragraph text does not leave 500 bookmarks in a Word file.

**Notes.** When confirmed this becomes `current`.
