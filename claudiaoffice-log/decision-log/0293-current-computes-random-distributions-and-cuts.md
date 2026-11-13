---
id: D293
title: "The distributions of RANDOM are quantile functions; a low/high cut squeezes the uniform number"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D293 · The distributions of RANDOM are quantile functions; a low/high cut squeezes the uniform number

**Every distribution is its quantile function applied to one uniform number** (`claudia_computes.distributions`, special functions in `claudia_computes.special`): uniform, normal, lognormal, triangular, pert, exponential, weibull, beta, gamma, binomial, poisson, discrete (values with weights). One uniform number per draw means common random numbers work (two cells with the same inputs and draw agree) and the export (D292) can write `INV(RAND(), …)`.

**A cut** (`low`, `high`) squeezes the uniform number into `[F(low), F(high)]` instead of rejecting and redrawing, so a draw is still one number and still deterministic; in Excel it is written with the matching `…DIST` function.

**Notes.** Parameters are checked when the cell is calculated; a wrong one is `#NUM!`/`#VALUE!` like in Excel.
