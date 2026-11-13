---
id: D295
title: "Outcomes: run the calculation over the cells that take part, once per combination; show the median"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D295 · Outcomes: run the calculation over the cells that take part, once per combination; show the median

**For every cell that depends on alternatives the engine knows the value under each combination of the alternatives it reads** (`claudia_computes.outcomes`). It finds the connected components of the input cells and their downstream closure, runs the normal `Calculator` round over just those cells per combination (with `calc.choice` set), and projects the result onto the inputs a cell actually reads. Above 10 000 combinations it takes a seeded sample (the sample is a function of the seed, D291), and random cells use common random numbers so alternatives are compared on the same draws. Summaries are refreshed only for components that went stale.

**The cell shows its median** (decided by the owner), the spread and the number of outcomes; the full table is a pop-over (D296). No `Simulate()` for now.

**Known limits.** Readers that find their precedents dynamically (OFFSET, INDIRECT) are not followed; an alternative that is a formula is evaluated with the other inputs' current choices.
