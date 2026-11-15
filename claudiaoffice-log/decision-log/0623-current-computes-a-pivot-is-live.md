---
id: D623
title: "A pivot is live: it follows its source and has no Refresh"
status: current
applies-to: computes
date: 2026-11-15
round: "Pivot tables (branch pivot)"
supersedes: []
superseded-by: []
---

# D623 · A pivot is live: it follows its source and has no Refresh

**Decided with the pivot's step two (2026-11-15), built as proposed.** Excel's pivot table has a Refresh button because its cache is a copy of the source. Claudia's would be recalculated like every other result of the engine: the reads of the query are recorded (D605) and the pivot is calculated again when the table it read changes, rows added below a table too (D603). There is no Refresh, and no pivot that shows what the source used to say.

**For:** it is what co-thinking asks for, and the same mechanism as `SQL()`. **Against:** a very large source recalculated on every edit (see the notes of D621), and a person who wants a frozen snapshot has to copy the values. A "freeze" could come later.

**How it is built.** The cell that starts a pivot holds `PIVOT("name")`, a formula like `SQL()` (D626): the calculator records what it reads and calculates it again when the source changes, and `SetPivot` calculates the cells that show it again. Writing a file (D625) must in any case write the cache and the cells as they are now.
