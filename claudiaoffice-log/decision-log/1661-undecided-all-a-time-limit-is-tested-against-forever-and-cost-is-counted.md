---
id: D1661
title: "A time limit is tested against forever, and cost is counted where it is spent in Python"
status: undecided
applies-to: all
date: 2026-11-25
round: "Test quality (branch test-quality): PROC-66, PROC-64 analysis"
supersedes: []
superseded-by: []
---

# D1661 · A time limit is tested against forever, and cost is counted where it is spent in Python

**Proposed 2026-11-25** on `test-quality`; undecided until the owner confirms it.

* **A test of a time limit** (a search's deadline, a model's timeout, a sandbox's) guards against work that never stops:
  a backtracking pattern on its test text would run for years. Its bound is far below forever and far above the limit:
  `claudia_search.testing.STOPPED_IN_TIME`, 5 s for deadlines of 0.1–0.3 s. A bound near the limit (0.6 s for 0.2 s)
  measured the machine: a busy runner took 0.7 s. Where the code reads a clock that can be injected, the test injects one
  and needs no bound at all (`ModelRunner(clock=)` with `FakeModel(clock=FakeTime())`).
* **A test of cost** (that something is linear, or does not grow with the size of what it skips) counts the Python work
  (`work_of` in `claudia-computes/tests/test_formula_performance.py`): the same on every machine. It measures time only
  where the cost is spent in C, where counting does not see it, and then with a ratio of best-of-N runs and a wide bound
  (as `test_letting_formulas_go_one_by_one_in_order_is_linear` does). Each counting guard has a test that breaks the code
  on purpose and sees the guard fail.
* **A time that is a security property** (SEC-04: a missing document costs what a wrong password does) is tested as the
  work that makes the time: the same password hashes at the same cost.

* **Where the cost may hide in C, the clock is processor time, gathered in batches** (`claudia_core.testing.best_of`):
  the time other programs take on a busy machine is not counted, and a fast case is run until it has used 0.2 s, so
  Windows' coarse processor clock is a small part of it. A linear guard measured 61x–71x for a 10x step in wall time
  under load; in processor time it passes.
* **A counted guard whose data lives in lists is backed by the clock** (the kernel's log): a slice is a copy in C, and a
  copy of the whole history per call counts as nothing. The backstop has three times the counted guard's room.

**Notes.** PERF-14 (2026-11-25) applied this to every Python performance guard: core (since, execute, undo, replay:
counted, with the clock as backstop; lookups: timed), composes (counted), computes (parse, edit, reopen, ranges, insert,
scratch, the grid window and the cell styles: counted; letting formulas go and the sheet extent: timed). Counted, they
measure 1.0x where flat and 9.9x–10.6x where linear. Checked against Python-level scans put in on purpose (since,
the grid window: caught) and a copy in C (since: caught by the backstop). The layout library's two TypeScript bounds
(4 s and 6 s for 100 pages) stay: JavaScript has no counter, and they are far from the measured time.
