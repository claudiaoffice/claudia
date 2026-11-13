---
id: D292
title: "replay_collecting: replaying a log needs nothing of a live Document"
status: current
applies-to: all
date: 2026-11-08
round: "Worker pool limits and heavy-call dispatch (thirty-first round)"
supersedes: []
superseded-by: []
previous-id: D178
---

# D292 · replay_collecting: replaying a log needs nothing of a live Document

**`claudia_core.replay_collecting(model, entries)` returns the `(entry, inverse)` pairs instead of taking an `on_applied` callback, and `Document.open`/`Document._rebuild` now call it and do their own undo-stack bookkeeping afterward, rather than handing `replay` a bound method of the live `Document`.** Groundwork only, per the owner's choice in the round's scope (`_rounds.md`): the replay loop — the CPU-bound part of opening a large document — is now a pure function of a model and plain log entries, with zero dependency on anything that cannot cross a process boundary (an event bus, a bound method holding one). Nothing dispatches it to a worker yet.

**Notes.** Behaviour-preserving: `test_document.py`'s `test_replaying_the_log_from_empty_gives_the_identical_state` and `test_history.py` pass unmodified, proving the undo stacks still come out identical. `materialize()` and the redaction-safety replay in `redact()` already took no callback at all and needed no change — only the two call sites that fed `replay` a bound method did.

Renumbered from D178 when the branch was brought up to `main` (2026-11-13).
