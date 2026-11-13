---
id: D291
title: "A heavy function defers, and its answer lands as a command"
status: current
applies-to: computes
date: 2026-11-08
round: "Worker pool limits and heavy-call dispatch (thirty-first round)"
supersedes: []
superseded-by: []
previous-id: D177
---

# D291 · A heavy function defers, and its answer lands as a command

**A `UserFunction` may declare `heavy = True` / `heavy_above = N`; `Bound.__call__` then raises `Deferred` instead of running it inline once the (already-converted) arguments pass that threshold, and `calc.py` carries the call through to resolution rather than blocking the round that hit it.** `Deferred` propagates uncaught up to `Round._calculate`, which freezes its arguments into a `FrozenGrid` snapshot (`functions/range.py`'s `freeze`) *at the moment of deferral* — D37's "a worker computes on a copy at revision r" — and files it in `Calculator.pending_heavy`. A worker's answer lands through the new `ApplyCalculated` command (`claudia_computes/commands.py`, `undoable = False`, the `Redacted`/`Checkpoint` precedent) via `Calculator.resolve_heavy`; `discard_heavy` retries the formula instead if the worker's answer is no longer wanted. Both guard with a plain "not pending → no-op," so a late worker answer racing a subsequent edit does nothing. Dispatch itself is `claudia_server/heavy_dispatch.py`'s new `HeavyDispatcher`, one per workbook document (`Hub`/`HostedDocument`, mirroring `Assistant`), submitting to the existing `WorkerPool` through a duck-typed `Submittable` so tests need no real process pool.

**Notes.** **Deliberately narrow, flagged rather than guessed around:** `Deferred` carries only the one call's own bound function and arguments, with no way back to whatever expression wraps it, so `HeavyDispatcher` only ever resolves a deferred call that *is* the whole formula (`=HEAVY(A1:A5)`, not `=HEAVY(A1:A5)+1`) — checked by `_is_whole_formula` against the compiled AST. A wrapped heavy call simply stays deferred, correct but unresolved, rather than risk landing a silently wrong answer; offloading part of an expression is a follow-up (see "Think ahead" in the round's notes, `_rounds.md`). No new event type was added for `HeavyDispatcher` to "wake up" on: `hub.py`'s broadcast loop calls `event.to_data()` on every emitted event unconditionally, so a new type would have become client-visible wire protocol, which the round's UI scope rules out — it reuses the document's existing event stream purely as a rescan trigger.

Renumbered from D177 when the branch was brought up to `main` (2026-11-13): D177–D179 had meanwhile been given to the shared object layer, a shape's SVG style vocabulary and composes objects. At the same merge the deferral was moved to the *end* of `Round._calculate`: a deferred formula goes through the same read-tracking and blocker pass as any other, and a query result it was filling is left as it was (D605, D606). Its arguments are still frozen at the same instant, after that pass and before anything else can change a cell.
