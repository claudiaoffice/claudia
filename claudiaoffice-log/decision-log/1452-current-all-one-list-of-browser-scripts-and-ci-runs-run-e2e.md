---
id: D1452
title: "One list of the browser scripts, in scripts/run_e2e.py; CI runs ./run-e2e.sh setup and regression like a computer"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard (E11.8, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1452 · One list of the browser scripts, and CI runs it through `./run-e2e.sh`

**Proposed in the tester review of 2026-11-21 (recommendation 2); the owner chose "one list" over a test that compares
two lists, 2026-11-22.**

`./run-e2e.sh regression` had its own list of the `web/e2e` scripts and CI's end-to-end job another; `objects.cjs` and
the two client-window scripts ran only in CI, so "use it before delivery" on a computer skipped the object contract
(PROC-44). Now:

- `SCRIPTS` in `scripts/run_e2e.py` is the one list: each script with where it runs (against one of the three shared
  servers or all of them, a server of its own, the house-fonts server, or the Windows or macOS client's window, built
  first) and its rough minutes.
- CI's job "End to end (Chromium)" installs the browser's system libraries (the one step a computer does by hand), then
  runs `./run-e2e.sh setup` and `./run-e2e.sh regression --no-setup`. It no longer calls any script by itself.
- `tests/test_ci_workflow.py` fails when `web/package.json` and `SCRIPTS` name different scripts, or when CI calls a
  browser script outside `./run-e2e.sh`.
- `./run-e2e.sh --list` counts the spec scenarios by collecting them, so its numbers cannot go stale (PROC-46).

**Consequences.** CI now also tests the runner's setup. Its screenshots and the logs of every script are kept when the
job fails. A failing script no longer stops the ones after it: the runner runs all and fails at the end, so one red
script does not hide the next (the lesson of 2026-11-21).
