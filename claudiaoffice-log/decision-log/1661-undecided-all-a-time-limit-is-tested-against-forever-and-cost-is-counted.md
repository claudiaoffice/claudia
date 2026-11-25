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

**Notes.** Of the performance guards that still read the clock (six in `test_formula_performance.py` besides the one
that must, and those of claudia-core, claudia-composes, the computes index and cell styles, and the layout library's),
none failed in the last 200 CI runs; converting them is proposed, not done. Counted, the six computes guards measure
10.6x, 1.0x, 9.9x, 1.0x, 10.0x and 1.0x, as stable as their bounds want; but a guard whose cost could move into C (the
scratch copy) needs its own "breaks on purpose" test before it may count.
