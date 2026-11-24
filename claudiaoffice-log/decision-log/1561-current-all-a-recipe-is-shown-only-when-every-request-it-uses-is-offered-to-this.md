---
id: D1561
title: "A recipe is shown only when every request it uses is offered to this asker"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1561 · A recipe is shown only when every request it uses is offered to this asker

**Decided 2026-11-23** (Q5), with one assumption of mine (the twin recipe) listed in the patch notes.

A recipe is a `## title`, a line `Uses: request, request`, and a few sentences with one worked example in the `commands` form.
`Guidance.skills_for(offered)` gives the text of the recipes whose requests are all among the requests this asker is offered, in
file order, under one heading. A person who may only look is offered no request that changes, so no recipe is shown to her: telling
a model how to use a request it may not make only invites a refused request.

**Composes has a twin recipe, "Propose a rewrite"**, which uses `suggest_words`. In suggest mode `replace_words` is not offered, so
"Rewrite a passage" is not shown and the model is taught to propose instead. An owner who acts is offered both requests and so
gets both recipes.

Four tests keep the files honest: every recipe names requests the app offers a model to change; every example is a request the
recipe names; every example gives the parameters its request takes and all it needs; and the server carries out every example on
a document that holds what it names (this last test found three wrong examples when it was first run: a replacement is a list of
`{"text": …}`, the heading style is `heading-1`, the shape is `circle`).
