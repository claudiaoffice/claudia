---
id: D294
title: "Alternatives {a, b, c} are formulas: =ALTERNATIVES(a,b,c), =SCENARIOS(name, …)"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D294 · Alternatives {a, b, c} are formulas: =ALTERNATIVES(a,b,c), =SCENARIOS(name, …)

**Typing `{800, 1000, 1300}` into a cell stores the formula `=ALTERNATIVES(800,1000,1300)`; a named one is `=SCENARIOS("name", 800, …)`.** The owner decided alternatives may themselves be formulas (`{=B2*2, 5}`), so they are ordinary formulas: references, structure edits (inserting rows), copy and the history work without new machinery. Only a **top-level** `ALTERNATIVES`/`SCENARIOS` call is an input; one alternative is no input; nested in another formula it is just a function returning its first value. An unnamed alternative is labelled `alt N`.

A cell with alternatives shows its first alternative's value everywhere else; `Sheet.alternatives` mirrors which cells are inputs.

**Notes.** The curly-brace typing is in `claudia_computes.alternatives`/`entry.py`; `TRUE`/`FALSE`-style literals are not touched.
