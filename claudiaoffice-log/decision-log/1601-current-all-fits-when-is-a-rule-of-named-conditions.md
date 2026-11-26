---
id: D1601
title: "Whether an entry fits is a rule made of named conditions, and a new condition is easy to add"
status: current
applies-to: all
date: 2026-11-25
round: "Menus that show what fits (menu work, branch `menus`, grilling of 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1601 · Whether an entry fits is a rule made of named conditions, and a new condition is easy to add

**Each action carries a rule "fits when", made of named conditions joined by and. The reasons and their first conditions:**

- **Role**: anyone · editor or owner · owner
- **Server**: has the tool for LaTeX / Mermaid / Typst
- **Client**: desktop only · web only
- **Document**: has a pivot table · has a table · has more than one sheet or slide · is being presented · …
- **Selection**: a cell or range · text · an object (of a kind) · a table · a chart · nothing
- **ai**: the ai can really answer (a model is set up, local or a provider such as Claude); the scripted stand-in does not count

**Several selected things: an entry fits only when it fits every one of them** (a text box and a picture selected: no Edit text). **A role change applies at once**, without reopening the document. **The implementation is abstract**: a condition is one named check with its reason and its "why" sentence, so a new condition is added in one place; the list grows only by decision, when a new entry needs a new word.

**Notes.** The owner added the ai condition: with only the stand-in, the entries that ask the ai (Ask ai in Tools and Help, the act/suggest switch) do not fit. Demos and tests that use the stand-in show them through the developer setting (D1606).
