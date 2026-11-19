---
id: D1305
title: "Imported slides, sheets, chart tabs and objects get generic names on import"
status: current
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1305 · Imported slides, sheets, chart tabs and objects get generic names on import

**Decided 2026-11-19** by the owner (E1.13): "imported things need to get generic names on import, e.g. 'Slide 1'".

Whatever the imported file does not name (D1303) is named **as part of the import**, in the language of the person who imports, with the same generic names new things get (D550): "Slide 4", "Text box 1", "Picture 2", "Chart 3". So an imported document has no thing without a name, and a tag in the chat can point at any of them at once; `name_unnamed` is then needed only for documents from before names.

**Notes.** *Assumption (to be confirmed):* this covers slides, sheets, chart tabs and objects, **not paragraphs**: D554 keeps naming a paragraph when somebody first points at it, because a text has hundreds and a name for each would be noise in every list. The names are part of the one `core.Import` entry (D438), so redacting an import blanks them with the rest.
