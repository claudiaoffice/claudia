---
id: D1453
title: "The browser scripts start their browser one way, web/e2e/browser.cjs, and $CLAUDIA_CHROMIUM names a browser already there"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard follow-up (E11.8, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1453 · One launcher and one variable for the browser of the scripts

**Asked for by the owner 2026-11-22 (PROC-52).**

The 30 scripts in `web/e2e` started Chromium in four ways: 8 read `CHROME`, 9 `CHROMIUM`, 2 `CLAUDIA_CHROMIUM` and 11
nothing, and two of them read `BROWSER=firefox` on their own. On a computer that cannot download Playwright's browser
(a sandbox, a proxy) most of them could not run. Now:

- `web/e2e/browser.cjs` exports `launch()`, the one way a script starts its browser: Chromium, from
  `$CLAUDIA_CHROMIUM` when it is set, else Playwright's own; Firefox with `BROWSER=firefox`.
- `$CLAUDIA_CHROMIUM` is the one name for a browser already on the computer, for the Python tests
  (`tests/e2e/test_greeting.py`, the specs) and the scripts alike. `CHROME` and `CHROMIUM` are not read any more.
- `tests/test_run_e2e.py` fails when a script calls `.launch(` itself or reads `CHROME`/`CHROMIUM`.

**Note.** That every script can be started in Firefox does not mean it passes there: CI runs them in Chromium (PROC-47).
