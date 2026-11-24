---
id: D1562
title: "The persona and the recipes are always on, and capped at 6,000 characters per app"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1562 · The persona and the recipes are always on, and capped at 6,000 characters per app

**Decided 2026-11-23** (Q6): always on, for every provider.

The local model gets the same persona and recipes as Claude. A test caps persona plus recipes of each app at 6,000 characters
(`MAX_CHARACTERS`); the files are about 2,500 to 3,100 characters today. The cap is what keeps a long prompt from costing a laptop
running a 7B model a slow first answer: the number to watch is the first-token time on the owner's machine, which was not measured
here (see the implementation note).

If it hurts, the loader can give the local model the persona and a shorter set of recipes without changing the files' format.
