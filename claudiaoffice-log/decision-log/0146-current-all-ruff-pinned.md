---
id: D146
title: "`ruff` is pinned to `>=0.6,<0.15`"
status: current
applies-to: all
date: 2026-11-06
round: "The Manage menu: leaving, handing over ownership, exporting and deleting (twenty-third round)"
supersedes: []
superseded-by: []
---

# D146 · `ruff` is pinned to `>=0.6,<0.15`

**`ruff` is pinned to `>=0.6,<0.15`.** Every release from 0.15.0 through 0.17.4 (the latest published) reformats a valid `except (A, B):` into the invalid `except A, B:` — confirmed by bisection, and by `ast.parse` raising a real `SyntaxError` on the result. `uv.lock` had already resolved the regressed version this round surfaced it under; this is how CODE-08's `ruff format .` broke 10 files (see CODE-10) at commit `558f429`, the very commit that added the `ruff format --check` gate it then silently failed.

**Notes.** Fixes CODE-10. No upstream fix exists at review time; the pin is removed once one does.
