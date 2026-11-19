---
id: D1241
title: "Behaviour is specified first, as Gherkin scenarios the owner reviews, and the scenarios run against the real server and a real browser"
status: current
applies-to: all
date: 2026-11-19
round: "Spec-first end-to-end tests (branch main, pilot: tables in composes)"
supersedes: []
superseded-by: []
---

# D1241 · Behaviour is specified first, as Gherkin scenarios the owner reviews, and they run against the real stack

**Decided by the owner 2026-11-19 ("more E2E tests, which we both specify in Gherkin or similar in an interactive mode").
Built for the tables of composes; the other features follow as they are touched.**

Recent "bugs" (a table drawn twice and not usable) were unspecified behaviour: to a person it was obvious that it did not
work, to the code it was not. So a feature now starts with what a person does and sees, written down and agreed before
the code.

- *Where.* `claudiaoffice-log/specs/<app>/<feature>.feature` (`composes`, `computes`, `creates`), `specs/objects/` for what all
  objects do alike, `specs/invariants/` for what every kind of object must do (once on the page, reload, undo, colleagues,
  files). The owner reviews them; the questions that remain are in `<feature>.review.md`. `specs/README.md` is the guide.
- *Tags.* `@core` (every delivery) and `@extended`; `@firefox` (also in Firefox); `@two-users`; `@desktop`;
  `@needs-decision` (what I propose, waiting for the owner: skipped); `@pending:<id>` (written, fails until the work behind
  `<id>` is done: expected to fail, and strict, so the day it passes the tag has to go); `@app:`, `@e2e:`, `@unit:`, `@io:`
  (where the check lives). `@after:<branch>` is gone: everything is merged.
- *Running.* `./run-e2e.sh core|extended|regression|all` sets up the machine (npm, the web build, Playwright browsers,
  fonts) and runs; step code is `tests/e2e/specs/` (pytest-bdd + Python Playwright, `conftest.py` and one `test_<feature>.py`
  per feature file). A step nobody has written code for **skips** its scenario and says which step: the skips are the honest
  list of what the specs promise and the tests do not check yet.
- *After every scenario*, whatever it did: no error in the browser's console, and a screenshot of the end state in
  `.claudia/e2e/shots` for a person to look at.
- *Bugs.* A bug fix starts with a failing scenario. "Use it before delivery" is the `@core` run plus a look at the shots.

**Notes.** Applies the owner's suggestion of 2026-11-19. Tooling: `pytest-bdd` is a dev dependency. Implementation note:
`notes/spec-first-e2e.md`.
