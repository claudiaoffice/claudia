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
    (E1.9), `invariants/objects-in-composes.feature` (PROC-40), `computes/slides.feature` (E6.31, merged from `main`
    while this branch was open: the guard caught it). `objects/the-same-in-all-three-apps.feature` was in it too until
    its step code came (follow-up below).
  * `test_a_draft_is_not_run_before_the_owner_has_approved_it`: bound and `@draft` at once fails.
  * `test_a_test_tag_names_a_test_that_exists_and_is_run`: `@unit:`/`@io:` paths exist; `@e2e:<script>` exists in
    `web/e2e/` and is in `SCRIPTS`. Only for files that run: a draft's or a waiting file's tags are promises.
  * `test_a_pending_tag_names_a_story_that_is_not_done`: `@pending:<story>` whose `_tasks/<story>-*.md` says
    `status: done` fails.
* `claudiaoffice-log/specs/objects/the-same-in-all-three-apps.feature`: marked `@draft`, then reviewed by the owner
  (the chart-tab scenario removed for the chart renames of E1.18) and approved, so `@draft` came off again.
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
* `scripts/run_e2e.py`, after the code review: `_record` says whether its command passed (the window scripts run only
  when their build did); `_stop_on_ci` makes a missing browser or font a stop on CI; `_free` probes a port with
  `SO_REUSEADDR` except on Windows (PROC-51, `tests/test_run_e2e.py`). `tests/conftest.py` (new) loads the runner once
  for the three tests that read it.
* `tests/e2e/specs/conftest.py` (PROC-48): `_launch(play)` picks the browser; the `browser` fixture skips with a reason
  when Playwright cannot start it.
* Docs: `specs/README.md` (the `@draft` tag; "every file is run, or says why not"), `specs/running.md` (one list, what
  runs, the skip message), story E11.8, decisions D1450–D1452, bugtracker round "E2E guard".

## Assumptions

* A tag on the `Feature:` line counts for all scenarios (pytest-bdd and the README already read it that way).
* The `@pending:<id>` check only looks at ids that name a story file; ids like `N2` (an owner's answer) are left alone.
* `scenario(file, name)` binds one scenario, so it does not count as binding a file; only `scenarios(...)` does.
* CI's job time: the job did the same work before (it already ran `objects.cjs` and both windows, 14 minutes on
  2026-11-22); the runner adds nothing the old steps did not do. The limit stays 30 minutes.

## Not done, from the code review

* The specs did not get a CI job of their own (WP2.4 of the plan): not needed at today's 14 minutes.
* `Script.runs` stays a string with four named groups rather than a type of its own: one module uses it.
* `_admin_fonts` still waits 10 s for its server to stop without killing it (as before).

## What could not be run here

* Firefox: not installed in this environment and not downloadable through its proxy; nothing in this change is
  Firefox-specific.
* The GTK client and the real Neutralino windows: unchanged by this work.

## Follow-up, 2026-11-22: step code for the cross-app spec, and one way to start a browser

* `tests/e2e/specs/test_the_same_in_all_three_apps.py` (new): the steps of
  `specs/objects/the-same-in-all-three-apps.feature` in all three apps, on one server of all apps.
  * Two people (14 rows): Ann inserts a picture or a shape, moves a container, renames a style (Format ▸ All Styles…)
    or changes the accent (Format ▸ Colours…); Ben sees it without reloading, and both after a reload.
  * Undo and redo of inserting (8 rows): the object goes and comes back, and the server forgets and brings back what it
    showed (D1454). `workbook | a chart` waits for CODE-77 in its own `Examples` block.
  * A viewer (15 rows), waiting for UX-69: Vera clicks the entries even when they are greyed, tries the rename and the
    colour controls if there are any, drags the object and a handle, Format ▸ Rotate, Delete. Nothing is sent, the
    document and the colleague's page stay as they were (all of that passes today); she is not told (UX-69).
  * A container needs LaTeX on the server: where the entry is off the scenario is skipped with that reason (CI's
    end-to-end job installs no LaTeX, so the six container rows of the two-people and undo scenarios skip there).
* `tests/e2e/specs/conftest.py`: `suite` (a server of all three apps, D430) and `suite_world`; `Person` takes an app,
  picks the kind of a new document on a server of several apps, waits for that app's page, keeps `sent` and `events`,
  and has `reopen()`; `menu(title, *path)` opens submenus; `world` and `suite_world` share `looked_after`.
* `web/e2e/browser.cjs` (new, D1453): `launch()`; all 30 scripts use it. `tests/test_run_e2e.py` checks that none starts
  a browser another way.

Assumptions: "I try to <change>" means clicking the entry even when it is greyed and using a control only where the
dialog shows one; "rename a style" renames the first style of the list; the palette change is the accent role.
