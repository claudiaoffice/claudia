---
id: D1310
title: "Every paragraph has a generic name from the start (\"Paragraph 1\"), and is renamed in Name & describe"
status: current
applies-to: composes
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1310 · Every paragraph has a generic name from the start ("Paragraph 1"), and is renamed in Name & describe

**Decided 2026-11-19** by the owner (E1.13, answering the open point about paragraph names in docx and odt): paragraphs are included in the rule that every thing has a name, and "they get generic names at first ('Paragraph 1')"; the dialog for changing a name is **Name & describe…**, the same as for objects (D1304).

**What this changes in D554.** D554 named a paragraph only **when somebody first pointed at it** (a heading by its own words, anything else by what it is), because a text has hundreds of paragraphs and a name for each was thought noise in every list. That part is **replaced**: a paragraph is named **when it is made** (and when an import brings it in, D1305, where D1305's "not paragraphs" is withdrawn), with the first free `Paragraph N` in the language of the person who makes it (D550). What D554 says about the kind of a paragraph (`heading`, `item`, `paragraph`), the id keeping the name through edits, the `#` list, Edit ▸ Reference in Chat and the tag scrolling to the paragraph **stands**. `name_unnamed` names the paragraphs of documents from before names too.

**Notes.** Still to settle, with proposed defaults, in D1311: how the `#` list copes with hundreds of generic names, numbering after inserts, splits and joins, whether a heading keeps its own words, what is written to docx and odt.
