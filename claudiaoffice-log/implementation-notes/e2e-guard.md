# E2E guard: every spec runs somewhere, and a computer runs what CI runs (E11.8; D1450–D1452)

Branch `e2e-guard`. Recommendations 1 and 2 of the tester review of 2026-11-21 (`notes/e2e-rework-plan.md`, WP0–WP2).

## What changed

* `tests/test_specs_are_bound.py` (new, D1450, D1451). Reads every `.feature` with the Gherkin parser pytest-bdd uses
  (`gherkin-official`), so it needs no browser and runs in the Python gate on all three systems.
  * `test_every_spec_file_is_run_by_a_test`: bound by `scenarios(...)` in `tests/e2e/specs/test_*.py`, or every
    scenario tagged `@unit:`/`@io:`/`@e2e:` (scenario, all its `Examples`, or the `Feature:` line), or `@draft`. The
    failure says the three ways out.
  * `NOT_BOUND_YET`: approved files that wait, each with its story. `test_the_list_of_files_not_bound_yet_only_shrinks`
    fails when an entry is run (or gone). Today: `objects/names.feature` (E1.13), `document-file/requirements.feature`
    (E1.9), `invariants/objects-in-composes.feature` (PROC-40).
  * `test_a_draft_is_not_run_before_the_owner_has_approved_it`: bound and `@draft` at once fails.
  * `test_a_test_tag_names_a_test_that_exists_and_is_run`: `@unit:`/`@io:` paths exist; `@e2e:<script>` exists in
    `web/e2e/` and is in `SCRIPTS`.
  * `test_a_pending_tag_names_a_story_that_is_not_done`: `@pending:<story>` whose `_tasks/<story>-*.md` says
    `status: done` fails.
* `claudiaoffice-log/specs/objects/the-same-in-all-three-apps.feature`: `@draft` on its `Feature:` line (it says
  "Draft for the owner's review, 2026-11-21"). Nothing else in it changed.
* `scripts/run_e2e.py` (D1452): the three lists (`WITH_SERVERS`, `OWN_SERVER`, `FONTS_ADMIN`) became one, `SCRIPTS`, a
  list of `Script(name, runs, minutes)`; `runs` is one of the three apps or `all` (the shared servers on 8765–8767),
  `own`, `fonts`, `windows` or `macos`. New in it: `objects`, `windows-shell`, `macos-shell`. The window scripts build
  `clients/neutralino` for their platform first (`build-windows`, `build-macos` appear as results of their own); setup
  runs `npm ci` there too (`_packages`, shared with `web/`). `--list` counts the spec scenarios with
  `pytest --collect-only -qq -o addopts=`. The help no longer says the step code is not built; the dead branch of
  `specs()` for a missing `tests/e2e/specs` is gone.
* `.github/workflows/ci.yml`, job `e2e`: `uv run playwright install-deps chromium`, `./run-e2e.sh setup`,
  `./run-e2e.sh regression --no-setup --shots "$SHOTS"`; on failure it keeps `shots/` and `.claudia/e2e/logs/`. The
  hand-written server start and the 30 `npm run e2e…` lines are gone.
* `tests/test_ci_workflow.py`: `test_every_browser_script_of_the_web_app_is_in_the_one_list` and
  `test_ci_runs_the_browser_scripts_through_the_one_list` replace the old grep of `ci.yml` (PROC-19's test).
* `tests/e2e/specs/conftest.py` (PROC-48): `_launch(play)` picks the browser; the `browser` fixture skips with a reason
  when Playwright cannot start it.
* Docs: `specs/README.md` (the `@draft` tag; "every file is run, or says why not"), `specs/running.md` (one list, what
  runs, the skip message), story E11.8, decisions D1450–D1452, bugtracker round "E2E guard".

## Assumptions

* A tag on the `Feature:` line counts for all scenarios (pytest-bdd and the README already read it that way).
* The `@pending:<id>` check only looks at ids that name a story file; ids like `N2` (an owner's answer) are left alone.
* CI's job time: the job did the same work before (it already ran `objects.cjs` and both windows); the runner adds the
  `npm ci` of `clients/neutralino` in setup, which the windows steps did before too. The limit stays 30 minutes.

## What could not be run here

* Firefox: not installed in this environment and not downloadable through its proxy; nothing in this change is
  Firefox-specific.
* The GTK client and the real Neutralino windows: unchanged by this work.
