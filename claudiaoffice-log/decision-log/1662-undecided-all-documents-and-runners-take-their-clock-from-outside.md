---
id: D1662
title: "The model runner and the memory provider take their clock from outside; a hosted document says when its pictures are made"
status: undecided
applies-to: all
date: 2026-11-25
round: "Test quality (branch test-quality): PROC-66"
supersedes: []
superseded-by: []
---

# D1662 · The model runner and the memory provider take their clock from outside; a hosted document says when its pictures are made

**Proposed 2026-11-25** on `test-quality`; undecided until the owner confirms it.

Three small changes of production code, made so that tests need no clock (D1660, D1661), in line with the kernel's rule
that clocks are injected (`claudia_core/clock.py`):

* `ModelRunner(model, …, clock=time.monotonic)`: the time limit of an answer is read on that clock.
* `MemoryProvider` stamps a new document with its `clock` option, as the documents it makes already do; before, it read
  the wall clock for that one time.
* `HostedDocument.rendered()` returns when every picture asked for so far has been made or given up, as
  `Assistant.idle()` does for questions. Nothing in the server calls it yet; tests do.

**Notes.** No behaviour of the server changes. Rejected: reading the private `_render_jobs` from the tests.
