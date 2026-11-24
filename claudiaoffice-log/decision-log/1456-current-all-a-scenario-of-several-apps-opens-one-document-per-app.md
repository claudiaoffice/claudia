---
id: D1456
title: "A names scenario tagged with several apps runs once, with one document per app it names"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard follow-up (E1.13 step code, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1456 · One run, one document per app

**Made while writing the step code of `specs/objects/names.feature`, 2026-11-22; for the owner to veto.**

Many scenarios of the names spec carry `@app:composes @app:computes @app:creates` and no `Examples`. Their steps say
"a text box, or a slide, or a sheet": each app does the part it can have (a sheet has no text box; a range name has no
spaces, so the far thing is "FarAway" in computes and "Far away" elsewhere).

The scenario runs once on the server of all three apps (D430). Its `Given` opens a new document of every app the
`@app:` tags name; every later step acts in each of them and its failure names the app. The alternative, one pytest run
per app, would have tripled the number of servers and documents the file starts and split steps that compare the apps.
A scenario with one `@app:` tag is the same with one document.

Where an app cannot have what a line is about, that app does nothing for the line, and nothing stands in for it:

- "a text box is on the page" (the right-click scenario): a sheet has no text box, so computes is left out;
- "the caret is in a paragraph (or a range of cells is selected)": a paragraph in a text box on a slide is not a thing
  of its own (Name & describe… there is for the selected object), so creates is left out;
- "I type, or click into the document": both are checked one by one where typing reaches the document from the
  keyboard (the text, the grid); on a slide typing needs a text box open for writing, which takes a click, so creates
  checks the click only.

Whether these scenarios should keep those `@app:` tags is a question for the owner (asked with this decision).
