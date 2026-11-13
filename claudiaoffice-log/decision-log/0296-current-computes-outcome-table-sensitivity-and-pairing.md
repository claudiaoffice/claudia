---
id: D296
title: "The outcome table lists every outcome with its alternatives, a sensitivity per input, and a paired mode"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D296 · The outcome table lists every outcome with its alternatives, a sensitivity per input, and a paired mode

**`outcome_table(sheet, row, col, combine)`** returns the inputs, one row per outcome (its value and the alternatives behind it), the summary, whether it was sampled, and a **sensitivity** per input (the mean outcome per alternative, widest swing first — a tornado). `combine="pair"` takes the first alternatives of all inputs together, the second ones, and so on (scenarios); inputs with different numbers of alternatives refuse it with a clear error.

Server methods: `outcome_table`; `cells` carries `alts` and `out` for a client to draw chips and medians.
