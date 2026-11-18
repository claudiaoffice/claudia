---
id: D1204
title: "No formulas in a composes table in the first version; a total per column and sorting only"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1204 · No formulas in a composes table in the first version; a total per column and sorting only

**A composes table has no formulas.** A column may have a **total** (`sum`, `mean`, `count`, `min`, `max` or none), shown as a last row in the total look; it is derived, never stored, and exported as an ordinary last row with the value as text. **Sort** reorders the rows with one command; row ids do not change; its inverse restores the order.

**Notes.** My earlier suggestion of formulas in a table's own scope "since the engine is shared" was wrong: the engine is in computes, the kernel may not hold it, and composes does not depend on computes. Formulas come later, through linked tables (E9.33), whose source can be a calculated column, or as their own decision. Confirmed 2026-11-18 ("formulas: later, not in v1").
