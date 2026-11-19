# Worker pool: what was salvaged from the branch `worker-pool` (E4.4, E3.5, D1314–D1316)

Branch `e1-core`, 2026-11-19. The owner asked for what is on `worker-pool` and not on `main` to be carried over where it
can be, and for the decision numbers to be cleaned up.

## What the branch was

Three commits (2026-11-08 to 2026-11-13; the last two only merged `main` into it). The first stage, the pool itself
(`WorkerPool`, D134), had gone to `main` with pull request #7. The branch added the second stage: heavy functions.
It was 208 commits behind `main`, and `git merge` would have conflicted in five files. Instead the branch's own change
(`git diff main...worker-pool`, 34 files) was applied to `e1-core` with a three-way merge, and the conflicts were
resolved by hand.

## What came over, and where it lives

| What | Where | Decision |
|---|---|---|
| `UserFunction.heavy`, `heavy_above`; `Bound.__call__` raises `Deferred` past the threshold | `claudia_computes/functions/base.py` | D1314 |
| `FrozenGrid`, `freeze`: the call's range arguments as a plain copy at the moment of deferral | `claudia_computes/functions/range.py` | D1314 |
| `Calculator.pending_heavy`, `resolve_heavy`, `discard_heavy`; the deferral at the end of `Round._calculate` | `claudia_computes/calc.py` | D1314 |
| `ApplyCalculated`: a worker's answer as a logged, non-undoable command | `claudia_computes/commands.py` | D1314 |
| `HeavyDispatcher`, `Submittable`; one dispatcher per workbook document | `claudia_server/heavy_dispatch.py`, `hub.py` | D1314 |
| `WorkerPool.max_waiting`, `PoolBusy`, `Hub(max_waiting=)` | `claudia_server/workers.py`, `hub.py` | D1316 |
| `replay_collecting`: replay as a pure function of a model and plain entries | `claudia_core/replay.py`, `document.py` | D1315 |

Five test files for the computes part, one each for the server's dispatcher, the pool and the hub, and one for the
kernel's replay came with it.

## What had to be adapted (the five conflicts, by hand)

* `calc.py`: `main` had meanwhile made a formula able to give a `Matrix` and a result that is blocked read the cells in
  its way. The deferral is merged *around* that: a deferred formula takes no part in spilling (`deferred is None`
  gates the `_spill`/`_unspill` branch), and goes through the same read tracking and blocker pass as any other. A
  `Deferred` raised inside `_evaluate` is let through, not turned into an error value.
* `hub.py`: `HostedDocument` and `Hub` now take `workers`, `renderings`, `original` and `uid` together, and `Hub` takes
  `max_waiting` as well; `Hub.max_documents` is a property of `Room` on `main`, so the branch's assignment is gone.
* `__init__.py` of three packages, and the two API snapshots (regenerated with `scripts/api_surface.py --write`, not
  merged by hand).
* Changelogs: the entries went under `[Unreleased]` (the three-way merge had put two of them under old versions).

## Decision numbers

The three decisions were D177–D179 on the branch, were renumbered to D291–D293 on 2026-11-13, and then collided with the
random-number decisions that `random-in-computes` had put on `main` under the same numbers. They are now **D1314–D1316**
in the range of this branch (`ranges.md`), each with `previous-id` (D291, D292, D293) and a line in the text that gives
the whole chain. Every citation in code, tests, changelogs and notes that was added by the branch was changed; the
random decisions keep D291–D299. The row for the branch in `ranges.md` was not brought over.

## What is true now, said plainly

* **No function in the library is heavy.** Nothing is dispatched to a worker in a running server today. The machinery
  is tested with test functions and waits for its first user (a library function that is measured slow, or a function
  from the parked function folder, D1313).
* **Only a call that is the whole formula resolves** (`=HEAVY(A1:A5)`, not `=HEAVY(A1:A5)+1`). A wrapped call stays
  deferred: correct, unresolved. Offloading a part of an expression needs `Deferred` to carry its way back to the
  expression: still open.
* **No "calculating" cell state** (E4.3): it needs a mock first.
* **Timeout, cancel, memory cap and crash containment are not there** (E3.5, SEC-19). The E0.2 spike's lifeline, watchdog
  and tree kill are the design for it.
* `replay_collecting` is groundwork: nothing sends the replay to a worker yet.

## Tests

`claudia-core`, `claudia-computes` and `claudia-server` suites, run package by package: green. `tests/test_public_api.py`,
`tests/test_decision_log.py`, `tests/test_changelog_versions.py`, `tests/test_docs_versioning.py` and ruff: green. Not
run: the end-to-end suite (nothing a browser sees changed), and a heavy function on a real process pool (none exists).

## Left for the owner

The branch `worker-pool` can be deleted once `e1-core` is merged; nothing of value stays on it. Its `_rounds.md`
section (the thirty-first round) came over with the text corrected.
