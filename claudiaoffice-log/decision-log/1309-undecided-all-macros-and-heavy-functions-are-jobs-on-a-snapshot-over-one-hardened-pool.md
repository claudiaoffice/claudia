---
id: D1309
title: "Macros, heavy functions and AI proposals are jobs on a snapshot over one hardened worker pool"
status: undecided
applies-to: all
date: 2026-11-19
round: "E1 core, closing out the open stories (branch e1-core)"
supersedes: []
superseded-by: []
---

# D1309 · Macros, heavy functions and AI proposals are jobs on a snapshot over one hardened worker pool

**Proposed 2026-11-19, not yet confirmed by the owner.** The owner asked for an analysis of the macro API (D239) and of the worker pool that was started for computes. The analysis, the proposal and the questions are in `notes/e1-macros-and-workers.md`.

In short: the pool of D134 gets what E0.2 found it needs (kill on timeout, cancel, memory cap, shared `Limits` with the subprocess sandbox, metrics); the `HeavyDispatcher` of branch `worker-pool` (D291–D293) becomes `DocumentJobs`, a job being a function run on a snapshot at revision r whose result is final values or commands, applied as one step if the footprint is unchanged. A **macro** is administrator-installed, trusted Python that reads a read-only view and returns the app's own commands; it acts as the person who runs it, as one undoable step tagged `via macro:<name>`; **a document never depends on a macro**, because replay never calls macro code.

**Notes.** When confirmed this decision settles D239 and completes D29's "or macros". It builds on D134, D291–D293, D436 and D1308. Branch `worker-pool` does not merge cleanly into `main` today (five conflicting files).
