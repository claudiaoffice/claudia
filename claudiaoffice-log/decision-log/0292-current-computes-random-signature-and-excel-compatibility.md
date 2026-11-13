---
id: D292
title: "RANDOM(dist, params…) is the signature; Excel gets the formula it would use itself"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D292 · RANDOM(dist, params…) is the signature; Excel gets the formula it would use itself

**`RANDOM()` is Excel's `RAND()`; `RANDOM("dist", params…)` draws from a named distribution.** The owner preferred this one function over a family of `RAND.X` functions, provided files open properly in Excel and OpenDocument programs. Export therefore writes each draw as the formula Excel itself would use (`NORMINV(RAND(), mean, sd)`, `LOGINV`, `BETAINV`, `GAMMAINV`, `CRITBINOM`, arithmetic on `RAND()` for uniform, exponential, weibull and pert, a `LOOKUP` for a literal discrete list) with the **legacy function names**, which every Excel and LibreOffice version reads without `_xlfn.`. Import reads those formulas back as `RANDOM`, so a round trip through Excel keeps the model's meaning.

A draw Excel has no single formula for (triangular, poisson, a discrete list that is not literal) is written as its current value and reported as a loss (D299). The numbers in the other program are of course its own: Excel recalculates `RAND()` on its own terms.

**Notes.** `RAND`, `RANDBETWEEN` work as in Excel (and are seeded the same way as `RANDOM`, D291).
