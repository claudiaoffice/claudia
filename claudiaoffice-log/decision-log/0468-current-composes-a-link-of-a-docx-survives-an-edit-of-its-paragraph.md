---
id: D468
title: "A hyperlink of a docx paragraph stays where it was when the paragraph's words are edited"
status: current
applies-to: composes
date: 2026-11-17
round: "Import and export wiring (branch import-export), IEW-01"
supersedes: []
superseded-by: []
---

# D468 · Links are carried through an edit of the words of a docx paragraph

**When a person edits the words of a paragraph of an imported docx that holds a hyperlink, the link element (`w:hyperlink`,
with its relationship and its run properties) is kept around the words of the new text that it covered before; a link
whose words were removed is dropped and listed as `removed-link`.**

**Notes.**

* *The bug.* python-docx counts the words of a link in `paragraph.text` but not in `paragraph.runs`. The patch wrote the
  new text as runs after the old runs were taken out, and the link, which was not among the runs, stayed: its words
  were in the file twice (IEW-01, existed since D217).
* *`_docx_links.carry_links(paragraph, before, after, anchors)`.* Finds the stretches of text that the old text and the
  new have in common (`difflib.SequenceMatcher`, `autojunk=False` up to 4,000 characters; common prefix and suffix
  beyond), and says for each link whether its words are still there and where. The writer puts the link element at that
  place and fills it with the words that are there, with the run properties it had; words typed inside a link join it,
  words typed beside it do not.
* *A link and a mark.* Marks of the paragraph (suggestions as tracked changes, D217) and links share one pass over the
  offsets, so a tracked insertion inside link words is still inside them.
* *Not here.* Linking words in Claudia (the model has no links); odt keeps `text:a` byte for byte outside the edit and
  was never affected.
