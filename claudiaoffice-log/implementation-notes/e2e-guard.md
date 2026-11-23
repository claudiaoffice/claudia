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
  * A container is a LaTeX one, left empty: where a server offers no LaTeX container (the entry is off) the scenario is
    skipped with that reason. CI's end-to-end job offers it and ran all six container rows (2026-11-22, run
    45048969323: 120 passed, 125 skipped, 19 xfailed in `tests/e2e`, as here).
* `tests/e2e/specs/conftest.py`: `suite` (a server of all three apps, D430) and `suite_world`; `Person` takes an app,
  picks the kind of a new document on a server of several apps, waits for that app's page, keeps `sent` and `events`,
  and has `reopen()`; `menu(title, *path)` opens submenus; `world` and `suite_world` share `looked_after`.
* `web/e2e/browser.cjs` (new, CODE-17, D1453): `launch()`; all 30 scripts use it; Firefox with
  `CLAUDIA_E2E_BROWSER=firefox`, as for the Python specs. `tests/test_run_e2e.py` checks that none starts
  a browser another way.

Assumptions: "I try to <change>" means clicking the entry even when it is greyed and using a control only where the
dialog shows one; "rename a style" renames the first style of the list; the palette change is the accent role.

After the code review of the follow-up: `eventually`, `Person.share` and `Person.notices` (every notice a page showed,
kept by an init script, since a notice goes away after 6 s) live in `conftest.py`, and the step files that had their own
copies use them (`test_administrators`, `test_caret`, `test_new_object_sizes`, `test_object_anchor`, `test_tables`,
`test_people`, `test_export`, `test_viewer`); `stack` and `suite` share `_web_server`; `World.join` refuses a second
person in another app. "After a reload we both see the same" compares with the place remembered before the reload, not
with Ann's page after it. "Shows the same as before" compares what the page shows (size, the picture, the outline).
While the viewer scenario waits for UX-69, its steps after "I am told" do not run; they passed when that step was
switched off by hand on 2026-11-22.

## Follow-up, 2026-11-22: step code for the names spec (E1.13)

* `tests/e2e/specs/test_names.py` (new) binds `specs/objects/names.feature`, which leaves `NOT_BOUND_YET`. All 28
  scenarios have steps; 21 pass in Chromium and lost `@pending:e1.13`. Six keep it, each failing for a reason of the
  story (the E1.13 story file lists them). "A new object, slide, sheet and chart tab have names" (not pending before;
  it never ran) now carries `@pending:UX-70 @pending:CODE-77`.
* `tests/e2e/specs/things.py` (new): what the cross-app spec and the names spec both use to find, insert and drag
  objects, moved out of `test_the_same_in_all_three_apps.py`.
* `conftest.Person.menu_item(label)`: an entry of the open menu whose label *starts* with `label`. `has-text` matched
  "Undo · Added a text box" for "Text Box" and undid the object it was to make. `web/e2e/objects.cjs` matches entries
  the same loose way; no run has shown it misfiring, so it is left as it is.
* Name & describe… is chosen from whichever menu has it (D1455: it is under Format today, the spec says Edit). A
  scenario with several `@app:` tags runs once with a document of each app (D1456).
* After a message is sent, the step takes the caret out of the chat box (`leave_chat`): while the box has the caret,
  a click on a thing in the document writes a tag for it (D551) instead of selecting it. That is the product working,
  not a bug; it made Ben's later clicks into tags and once looked like a bug of renamed tags.
* "Where the view is" is read as the way back counts it (D1312): the text's first paragraph under the top of the
  scroller, the sheet's top-left cell, the slide shown; and only once the smooth scroll of a jump has stopped.

After the code review of this follow-up:

* No fixed waits: a step waits for the view it expects or for the view to stop moving (`steady`, `where`,
  `moved_from`, `back_at`, `jump`). "I wait a minute" runs the page's clock a minute on (`page.clock`), not the test's.
* "The option about comments is not there" is judged only after the server has answered how many descriptions there
  are: `Person.answers` keeps the results of a page's requests, as `sent` and `events` keep the rest of the wire.
* "I type, or click", and "View ▸ Back where I was, or Ctrl+Shift+B" check each of the two on their own, after the same
  jump again. "The description can" saves one and reads it back. "Marked for a moment" checks the paragraph is on screen
  and the mark goes. "Introduction (2)" is read on the later heading, "Introduction" on the first.
* `Person.finish_import` answers the import dialog for this spec and `test_export.py`; `things.FIRST_CELL` and
  `things.insert(person, "a text box")` are shared; `insert_container` uses `menu_item`.
* In computes, after a rename the step waits until the Name Box shows the new name. Once, going on at once to the
  next cell ("A300" typed into the Name Box) left the selection where it was; why was not found (the likeliest reading,
  not proven: the Name Box took the new name after the step had typed). Not logged as a bug.

CI on `e2e-guard` (2026-11-23):

* The end-to-end job failed twice with "1 failed, 140 passed" and did not say which test: fixed as PROC-52
  (`pytest_command` asks for `-rfEs`; a failed run prints pytest's `FAILED`/`ERROR` lines first). Its test is skipped
  on native Windows, where the runner does not run (WSL); on Windows the printed output did not hold the failed test's
  name, and why was not looked into.
* The next run named "A document without descriptions does not offer the option" ("the dialog got no answer"), which
  failed locally 2 times in 6 as well. The sync Playwright API hands a page's websocket frames to Python only while a
  Playwright call runs; `eventually` slept in `time.sleep`, so the answer stayed undelivered. `eventually(..., page=)`
  now waits on the page between tries; the names step and two checks of the cross-app spec that read `Person.events`
  pass their page (those two had not failed: an earlier wait on the page had delivered the frames). 8 runs of 8 passed
  after the change.
* A full local run then failed once on the cross-app row `workbook | move a container`: Ann's container place was
  remembered as soon as it differed from before, and a dropped object can still settle where the server puts it
  (Ben's page showed 148/78, Ann's had been read at 132/66). It is now remembered once it stops moving (`steady`, moved
  to `conftest.py` for both spec files). It passed 10 times of 10 alone before the change; the race shows under load.
* The Python jobs failed on `test_calculating_a_long_chain_is_linear` (44x and 45x instead of about 10x): PROC-44, open,
  not touched by this branch; green on a rerun.

Assumptions: "my own language" is English (the browser's language in the runs); a sheet named "Sheet2" is "a name like
Sheet 2"; a range's names have no spaces ("DescribedCells", "FarAway"); Ben deletes a paragraph by selecting from the
end of the one before it, so the first paragraph stays; Ann's caret is moved away first, because the place around a
person's caret is hers while she is there.

What could not be run: Firefox (not in this environment); the GTK client and the Neutralino windows (the spec is run
in the web client only, as all specs are).
