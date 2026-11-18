---
id: D1207
title: "An own table has at most 100 rows and 10 columns at first"
status: current
applies-to: composes
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1207 · An own table has at most 100 rows and 10 columns at first

**A table in a text has at most 100 rows and 10 columns.** The kernel refuses a command that would go beyond, and says what to use instead: a linked table (E9.33) or a computes table (E4.12) for more. The limits are constants of `claudia_core.tables` (`MAX_ROWS`, `MAX_COLUMNS`), so raising them is a one-line change with a test.

**Notes.** My first guess was 500 rows and 30 columns; the owner chose 100 and 10 on 2026-11-18. Cell words are bounded by the paragraph's own limits.
