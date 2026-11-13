---
id: D347
title: "Which Markdown the notes allow, and how they pass through ODP and PPTX, is proposed and not decided"
status: undecided
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D347 · Which Markdown the notes allow, and how they pass through ODP and PPTX, is proposed and not decided

**Undecided.** Proposal: CommonMark without raw HTML and without images; paragraphs, emphasis, strong, lists, headings (shown as bold lines), links, inline code, block quotes; rendered from a parse tree, never by inserting HTML. ODP and PPTX notes pages carry text with runs and bullets: the writers map bold, italic, lists and headings to them, the readers map them back, and anything else stays plain text. Both formats' notes pages are written and read in the same patch as the notes themselves (project rule). The Markdown parser's licence must fit the GPL stance like every component.

**Notes.** Follows D342. `notes/e10-2-presenter-mode.md`, open point A.
