# Spec-first end-to-end tests: how the pieces fit (D1241)

**What it is.** A feature starts as Gherkin in `claudiaoffice-log/specs/`, which the owner reviews. The scenarios run
against a real server and a real browser. A bug fix starts with a scenario that fails.

**Pieces.**

| Piece | Where | Notes |
|---|---|---|
| Scenarios | `claudiaoffice-log/specs/<app>/*.feature`, `objects/`, `invariants/` | tags: see `specs/README.md` |
| Step code | `tests/e2e/specs/conftest.py`, `test_<feature>.py` | pytest-bdd 9 (a dev dependency), Python Playwright |
| Server | session fixture `stack` | `live.server(..., "--model", "claudia_composes:TextModel", "--web", web/.output/public)`; one server per run, one document per scenario |
| Browser | session fixture `browser` | Chromium (or `$CLAUDIA_CHROMIUM`), Firefox with `CLAUDIA_E2E_BROWSER=firefox` (only `@firefox` scenarios) |
| Runner | `./run-e2e.sh` → `scripts/run_e2e.py` | set-up (npm, web build, browsers, fonts) and then `core`, `extended`, `regression`, `all` |

**Rules the harness enforces** (`conftest.py`): `@needs-decision` is skipped; `@pending:<id>` is `xfail(strict)`; a scenario
with a step that has no code is skipped *before* its Background runs, naming the step; after every scenario the browser
console must have no error, and a screenshot is saved.

**Writing a step.** Put it in the `test_<feature>.py` of the feature, in a person's terms (menu entries, keys, what the
boxes read, where the caret is). `Person` in `conftest.py` has the page and a few readers (`order()`, `boxes()`,
`focused_box()`). Steps do not poll the server or read the app's state: they look at the page. After an action that goes
to the server, wait with `eventually(...)`, and for "once" and "still there" checks also `settle(...)` (a late echo that
doubles a word comes after the first look).

**Traps found while building it.**
- A person's hands are slower than Playwright's. A scenario that has to be robust against quick hands (B2, B4) says so in
  its words ("when my hands are quick") and the step does no pause; the others can wait.
- `selectionchange` reaches the app a moment after a click. Code that acts at the caret on a key, a menu entry or a dialog
  must read the caret from the page first (`TextEditor.syncCaret`, D1243).
- Vue patches a textarea's `value` on every redraw. Words typed and not committed have to live in a draft (`TableView.vue`).
- Python Playwright's `goto` waits for `load`, which the app reaches late on a cold server: the harness waits for
  `domcontentloaded` and then for the form.

**Not built yet.** Firefox runs (not run in this workspace: no browser to download); `@two-users` steps; most `@extended`
steps; server-side errors as an always-check; the desktop clients (`@desktop`). Of 97 scenarios of `tables.feature`, 11
have step code (9 pass, 2 are `@pending:N2` and fail as meant); the other 86 skip, each naming the missing step.
