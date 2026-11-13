---
id: D299
title: "Both exports report their losses: random draws written as values, alternatives written as one value"
status: current
applies-to: computes
date: 2026-11-13
round: "Random numbers, alternatives and following a computation (branch random-in-computes)"
supersedes: []
superseded-by: []
---

# D299 · Both exports report their losses: random draws written as values, alternatives written as one value

**`xlsx_export_losses` joins `ods_export_losses`: after an export the server answers `losses` for xlsx as well** (`{kind, detail, count}`), so the interface can say what the file could not hold: kind `formula` with detail `random` (a draw Excel has no formula for, D292) and kind `alternatives` (D298). An export with nothing lost answers an empty list.

**Notes.** `export_office` for xlsx used to answer no `losses` key; a client that ignored it keeps working.
