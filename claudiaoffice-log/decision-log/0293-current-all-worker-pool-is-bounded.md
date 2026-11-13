---
id: D293
title: "The worker pool is bounded: max_waiting and PoolBusy"
status: current
applies-to: all
date: 2026-11-08
round: "Worker pool limits and heavy-call dispatch (thirty-first round)"
supersedes: []
superseded-by: []
previous-id: D179
---

# D293 · The worker pool is bounded: max_waiting and PoolBusy

**`WorkerPool` gains `max_waiting`, bounding how many submissions may be in flight at once the same way `Assistant.max_waiting` already bounds queued AI turns.** Once `max_waiting` submissions are in flight, `WorkerPool.submit` raises `PoolBusy` immediately, before anything is queued or sent to the executor — never silently queued, never run inline as a fallback. `HeavyDispatcher` treats `PoolBusy` as "try again next time something wakes this document," not an error.

**Notes.** Mirrors `Assistant`'s existing shape deliberately, so the two "the server is too busy for this kind of work right now" signals behave the same way for callers.

Renumbered from D179 when the branch was brought up to `main` (2026-11-13).
