---
id: D1450
title: "Every spec file is run by a test, or says which test checks it; the files that cannot be run yet are listed with their story"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard (E11.8, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1450 · Every spec file is run by a test, or says which test checks it

**Proposed in the tester review of 2026-11-21 (recommendation 1), agreed by the owner 2026-11-22.**

On 2026-11-21 four approved files in `claudiaoffice-log/specs` were read by no test and not even counted as skipped
(PROC-40), so "the E2E specs pass" said nothing about them. `tests/test_specs_are_bound.py` now fails when a
`.feature` file is

- not bound by `scenarios(...)` in a `tests/e2e/specs/test_*.py`,
- and not every one of its scenarios carries `@unit:<path>`, `@io:<path>` or `@e2e:<script>` (on the scenario, on all of
  its `Examples`, or once on `Feature:`),
- and it is not a draft (D1451).

An approved file that cannot be bound yet stands in `NOT_BOUND_YET` in that test, with the story or bug that binds it.
The test fails when an entry is no longer needed, so the list only shrinks; adding to it is the owner's call, not a way
to get CI green. On 2026-11-22: `objects/names.feature` (E1.13, after the chart renames of E1.18),
`document-file/requirements.feature` (E1.9), `invariants/objects-in-composes.feature` (PROC-40).

The same test checks that a test tag names a file that exists and, for `@e2e:`, a script `./run-e2e.sh regression`
runs (D1452); and that `@pending:<story>` does not wait for a story whose file says `status: done`.

**Notes.** The test reads the files with the Gherkin parser pytest-bdd uses (`gherkin-official`), so it needs no browser
and runs in the Python gate on all three systems. Implementation note: `implementation-notes/e2e-guard.md`.
