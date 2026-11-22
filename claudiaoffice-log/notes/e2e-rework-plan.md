# E2E rework: a work plan for a long, mostly unsupervised run

**Status 2026-11-22: recommendations 1 and 2 are done (WP0 to WP2), the rest waits.** The owner narrowed the work to
those two because of parallel work (the menu rebuild, the chart renames of E1.18). They were done on branch
`e2e-guard` as story E11.8, decisions D1450–D1452 (implementation note `implementation-notes/e2e-guard.md`). Two things
came out differently from this draft: the JSON list WP2 proposed became `SCRIPTS` in `scripts/run_e2e.py`, and CI runs
`./run-e2e.sh` itself (D1452); and `computes/pictures-in-files.feature` was not lost (its `Feature:` line carries an
`@io:` tag), so three approved files wait, not four. WP3 to WP8 are kept here for when the owner restarts them; their
branch, story and decision ids are to be agreed again then.

**Written:** 2026-11-21, as a draft for the owner's review. **Source:** the tester review of 2026-11-21 (recommendations
1–5; findings PROC-40, PROC-46 to PROC-48, PROC-50; the first draft's ids were renumbered where other work had taken them).

This note is written for an orchestrating agent that starts cold and spawns sub-agents. Read the project instructions,
`CONTRIBUTING.md`, `claudiaoffice-log/specs/README.md`, `claudiaoffice-log/specs/running.md` and
`claudiaoffice-log/coding-standards.md` before anything else; this plan does not repeat them and never overrides them.

---

## 0. What the run is for, and what it is not for

**In scope (recommendations 1–5 of the review):**

1. Every scenario in `claudiaoffice-log/specs` is run somewhere, or the build fails (PROC-40, widened).
2. Running the E2E tests on a computer runs what CI runs (PROC-50, PROC-46, PROC-48).
3. Firefox runs in CI (PROC-47).
4. The invariants file becomes the backbone: every kind of object, in every app that has it, passes the same scenarios.
5. First spec-first journeys for computes and creates, plus four cross-app journeys, **drafted** for the owner's review;
   step code only for what the owner has approved.

**Out of scope:** new product features; the 71 table steps without code (recommendation 8); the GTK/AT-SPI journeys
(recommendation 7); the pseudolocale I18N run (recommendation 6); rewriting the `web/e2e/*.cjs` scripts (D1241 says
they stay); the menu rebuild of `claudia-menus.xlsx` version 5.

**Measured starting point (main @ `d18c4e4`, Chromium, 2026-11-21):** 251 scenario headers in 17 files; 202 collected
from the 10 bound files: 76 pass, 124 skip (76 without step code, 32 "checked by" a unit/io/e2e tag, 15 waiting for a
decision, 1 missing LaTeX), 2 xfail (`@pending:N2`); 0 fail; 5½ minutes. Seven files are not bound to any test.

---

## 1. Roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **Owner** | the human | answers section 2 up front; approves new scenarios at gate G2; accepts the result at G3 | — |
| **Orchestrator** | one agent, the only one that commits to `e2e-rework` | keeps `notes/e2e-rework-progress.md`; starts sub-agents per work package; merges their patches in order; runs the full suites; merges `main` in daily; writes the report | writes product code itself; approves its own work |
| **Worker** | one sub-agent per work package (WP), in its own git worktree | the WP's steps, test first; returns a patch plus a short note (what changed, what it ran, what it could not run, bugs found) | touches files owned by another WP (section 4); edits scenario wording; merges |
| **Reviewer** | a fresh sub-agent that has not seen the work | runs `/code-review` on each patch against this plan and the guardrails (section 3); re-runs the WP's acceptance commands itself | fixes the code (it reports; the worker fixes) |

---

## 2. Decisions the owner makes before the run starts

Each has a proposed default; the owner only vetoes. The orchestrator records the answers at the top of
`notes/e2e-rework-progress.md` and does not start WP1 until every line has an answer.

| # | Question | Proposed default |
|---|---|---|
| O1 | Where does the run happen? A cloud session cannot download Playwright's browsers (no Firefox) and was refused push access on 2026-11-21. | On the owner's computer, in the local clone, through the desktop app (Firefox there; ports 8765–8768 free, so no `./start.sh` meanwhile). Alternative: a cloud session **with** push access, Firefox checked only in CI. |
| O2 | May the run push `e2e-rework` to GitHub to see CI (needed for Firefox if O1 is the cloud)? | Yes, the feature branch only; never `main`, never force-push. |
| O3 | Which new scenario text needs the owner's approval before step code? | (a) Binding an already approved file: no review. (b) A new row in the `Examples` of the invariants: no review (the file says new kinds are added as rows). (c) Rewording or moving an approved scenario into the cross-app invariants file: review (G2). (d) A new feature file (WP7): review (G2). |
| O4 | What happens to product bugs the new tests find? | Logged, not fixed: a `bugtracker.md` entry with size 1–3, and the failing scenario tagged `@pending:<BUG-ID>` (strict xfail, so the day the bug is fixed the tag has to come off). The run stops and asks if it finds a size-1 bug. |
| O5 | May workers change product code for testability? | Only attributes (`data-testid`, ARIA roles and names that are missing anyway); no behaviour, no layout, no strings. Each one listed in the patch notes. |
| O6 | Firefox in CI: when? | `@firefox` scenarios on every push (they are few); every `@core` scenario in Firefox nightly. |
| O7 | The invariants: today's object kinds per app (the `KINDS` table of `web/e2e/objects.cjs`), or the target of `claudia-menus.xlsx` (which promises text boxes and shapes in computes too)? | Today's kinds as rows that must pass; kinds the workbook promises but the app lacks as rows tagged `@pending:<story>`. |
| O8 | The invariants: one file for all apps, or one per app? | One file, `specs/invariants/objects.feature`, with columns `app` and `kind`; the old `objects-in-composes.feature` is folded into it (its approved scenarios keep their words; only `<app>` is added). |
| O9 | Which export formats do the invariants round-trip? | Per app: the Claudia file, one Office format and one OpenDocument format (composes docx + odt, computes xlsx + ods, creates pptx + odp). |
| O10 | Which WP7 journeys, in what order? | Section 5, WP7 list, in that order. The owner may strike any. |
| O11 | How much may CI's E2E time grow? | The `e2e` job stays under its 30-minute limit; the specs move to a job of their own (Chromium) and a Firefox job, each under 20 minutes. |
| O12 | How is the result delivered? | One patch per WP against `e2e-rework` (never a bundle), in the order of section 5; the owner merges to `main` after G3. |
| O13 | Budget and check-ins. | The run stops for good after the gates G2 and G3, or after 3 working sessions, whichever is first; a progress line in `notes/e2e-rework-progress.md` after every WP; a push notification at each gate. |
| O14 | The stale `e2e` branch on GitHub. | Left alone; the owner deletes it if wanted. |

---

## 3. Guardrails (for every agent in the run)

**Honesty of the suite: the most important rules.**

1. Never make a test pass by weakening it: no looser assertion, no longer timeout without a reason in the note, no
   removed `Then`, no `@needs-decision`, `@extended`, skip or xfail added to hide a failure. A red scenario stays red
   and gets a bug entry (O4).
2. Never change the words of an approved scenario. A step that does not fit the app goes into a
   `<feature>.review.md` question, not into the `.feature`.
3. `@pending:<id>` comes off only in the commit where the scenario passes; it is never removed by hand otherwise.
4. Every new assertion is checked once for the right reason: break the behaviour on purpose (or run against `main`
   before the fix), see it fail, then restore. The note says how this was seen.
5. A flaky scenario (passes and fails on the same code) is not retried until green. Run it 20 times, record the rate,
   file a bug (like UX-59), and tag it `@pending:<BUG-ID>` only if the owner agrees at the next check-in.

**Scope and safety.**

6. No product behaviour changes (O5 is the only exception). No change to `main`. No force-push. No deleted branches.
7. Files have one owner at a time (section 4). A worker that needs a file owned by another WP stops and tells the
   orchestrator.
8. Merge latest `main` into `e2e-rework` at least daily and before every patch is delivered; a conflict in product code
   is stopped and asked about, not resolved by guessing.
9. Menu entries are reached through one helper that knows the entry by its row in `claudia-menus.xlsx` (or the key table
   behind `keys.cjs`), not by its label typed into each step; the menu rebuild will rename entries.
10. Stop and ask the owner (push notification, then wait) when: a size-1 bug is found; CI is red for a reason outside
    the run's files after 2 attempts; a guardrail would have to be broken to go on; a decision in section 2 turns out
    not to cover a case; a WP takes more than twice its estimate.

**Evidence.**

11. Every patch note follows the project's "done" report: branch, commit, what ran (with numbers before and after),
    what could not be run, bugs found with size, assumptions, debt seen.
12. The reviewer re-runs the acceptance commands itself; a WP is not done on the worker's word.

---

## 4. Files and who owns them

| File(s) | Owner WP |
|---|---|
| `tests/test_specs_are_bound.py` (new) | WP1 |
| `scripts/run_e2e.py`, `run-e2e.sh`, `claudiaoffice-log/specs/running.md`, `web/e2e/scripts.json` (new) | WP2 |
| `.github/workflows/ci.yml` | WP2, then WP3 (in that order, never at once) |
| `tests/e2e/specs/conftest.py` | WP2 (browser fixture), then WP3 (Firefox switch), then WP5 (shared steps); never two at once |
| `tests/e2e/specs/test_names.py`, `test_requirements.py`, `test_pictures_in_files.py` (new) | WP4 |
| `claudiaoffice-log/specs/invariants/*`, `tests/e2e/specs/test_invariants.py`, `tests/e2e/specs/kinds.py` (new) | WP5 |
| `claudiaoffice-log/specs/computes/*`, `creates/*`, `journeys/*` (new feature drafts and `.review.md`) | WP7 |
| `claudiaoffice-log/bugtracker.md`, `decision-log/*`, `ranges.md`, the E11.8 story, `notes/e2e-rework-progress.md` | orchestrator only |

---

## 5. Work packages

Order and parallelism: **WP0 → WP1 → (WP2 ∥ WP4 ∥ WP7 drafts) → WP3 → WP5 → G2 → WP7 step code → WP8.**
WP5 waits for WP2 because both touch `conftest.py`.

### WP0: Baseline (orchestrator, about 1 hour)

1. Merge `backlog` into `main` as the project instructions say; branch `e2e-rework` from `main`; push the `ranges.md`
   reservation (D1450–D1469) to `main` and the branch, as the instructions say.
2. Add story E11.8 (from section 0) to `Projects/claudia-office/_tasks/`.
3. `./run-e2e.sh setup`, then `./run-e2e.sh extended --browser both` and `./run-e2e.sh regression`; record pass/skip/fail
   counts per file in `notes/e2e-rework-progress.md`. In the cloud, `CLAUDIA_CHROMIUM` may point at a preinstalled
   Chromium; say that Firefox could not run.
4. Run `@core` 5 times to find flaky scenarios before anything changes; record them.

**Acceptance:** the progress file has the baseline table and the flaky list.

### WP1: Nothing runs nowhere (worker, about half a day)

1. Write `tests/test_specs_are_bound.py`, red first. It fails when:
   - a `.feature` file under `claudiaoffice-log/specs` is neither bound by `scenarios(...)` in `tests/e2e/specs/`
     nor has a test tag (`@unit:`, `@io:`, `@e2e:`) on every scenario (a tag on `Feature:` counts for all);
   - a tag names a path that does not exist;
   - an `@e2e:<script>` names a script that is not in the list CI **and** `./run-e2e.sh regression` run (this part goes
     green with WP2);
   - a `@pending:<id>` names a story whose file in `_tasks/` says `status: done`.
2. Expected red today: `objects/names`, `invariants/objects-in-composes`, `container/requirements`,
   `computes/pictures-in-files`; and `@e2e:objects.cjs` (not run locally).
3. Mark the reds the run fixes later as known, in one list inside the test with the WP that fixes each. The list may
   only shrink; the test fails if an entry is no longer needed.
4. Update PROC-40 in `bugtracker.md` (orchestrator): seven files, not four.

**Acceptance:** the test is red without the known-list and green with it; the known-list has 5 entries, each naming a
WP.

### WP2: Your computer runs what CI runs (worker, about half a day)

1. One list of the `web/e2e` scripts, `web/e2e/scripts.json`: name, which server(s), extra environment, minutes. Both
   `scripts/run_e2e.py` and the CI `e2e` job read it (CI through a small step that loops over it, or a test that fails
   when `ci.yml` and the list differ; choose the smaller change and say why). `objects`, `windows-shell` and
   `macos-shell` join the local `regression` run (PROC-50).
2. Fix the stale texts: the help and `--list` of `run_e2e.py`, and `running.md` ("11 of 97") (PROC-46). `--list`
   prints the real counts by collecting with pytest, so it cannot go stale again.
3. The `browser` fixture of `tests/e2e/specs/conftest.py` skips with the same reason as `test_greeting.py` when no
   browser can be launched, instead of failing (PROC-48).
4. The specs get their own CI job (`End to end specs (Chromium)`), separate from the 30-minute `e2e` job (O11).

**Acceptance:** WP1's `@e2e:` check is green; `./run-e2e.sh regression --list` shows 30 scripts; on a machine without
browsers the specs report "skipped: no chromium …"; CI is green with the new job.

### WP3: Firefox in CI (worker, about half a day, after WP2)

1. A `End to end specs (Firefox)` job: `uv run playwright install --with-deps firefox`, then
   `CLAUDIA_E2E_BROWSER=firefox uv run pytest tests/e2e/specs` (which runs `@firefox` only). It runs on every push (O6).
2. A nightly schedule runs every `@core` scenario in Firefox: an environment switch (e.g. `CLAUDIA_E2E_ALL_CORE=1`) in
   `conftest.py` keeps `@core` as well as `@firefox`. Coordinate the `conftest.py` change through the orchestrator
   (section 4).
3. Every scenario that passes in Chromium and fails in Firefox is a bug (O4), size 2 by default, with the browser
   named in its title.

**Acceptance:** both jobs exist; the push job is green or every red scenario has a bug entry and a `@pending:` tag
agreed at a check-in; PROC-47 closed.

### WP4: Bind the files that run nowhere (worker, 1–2 days; may be split into one worker per file)

1. `objects/names.feature` → `test_names.py`. E1.13 is still `in-progress`; keep `@pending:e1.13` on each scenario
   until it passes, then remove it in that commit. Reuse what `tests/e2e/test_things_have_names.py` and
   `web/e2e/dock.cjs`, `dock-text.cjs` already know about names and `#` tags.
2. `container/requirements.feature` → `test_requirements.py`; `@needs-decision` scenarios stay skipped;
   `@pending:e1.9` as above.
3. `computes/pictures-in-files.feature`: four scenarios are file-format facts. Give each an `@io:` tag pointing at the
   test in `claudia-computes-io` that already checks it, or write that test there; bind the rest.
4. `objects/selecting-and-keys`, `turning`, `words`: keep `@e2e:objects.cjs`, but add a comment in `objects.cjs` next to
   each check naming the scenario it covers, and a check in WP1's test that every scenario title of these files
   appears in such a comment (traceability per scenario, not per file).
5. `invariants/objects-in-composes.feature` is handled by WP5, not here.

**Acceptance:** WP1's known-list loses four entries; the counts per file are in the progress file.

### WP5: The invariants as the backbone (worker, 2–3 days, after WP2)

1. Fold `invariants/objects-in-composes.feature` into `invariants/objects.feature` (O8): the approved scenarios keep
   their words, with `<app>` added ("a new composes document" becomes "a new <app> document"). This rewording goes
   to the owner at G2 (O3c), so prepare it first and continue with step code on the composes rows meanwhile.
2. `Examples` rows: every pair of app and kind from `KINDS` in `web/e2e/objects.cjs` that the app can make (O7). Today:
   composes text box, shape, picture, container, table; computes picture, container, chart; creates text box, shape,
   picture, container. Kinds that `claudia-menus.xlsx` promises but the app lacks get rows tagged `@pending:<story>`.
   Add paragraph-level things (heading, list) as rows only where the scenario makes sense; otherwise a
   `.review.md` question.
3. `tests/e2e/specs/kinds.py`: one adapter per (app, kind), how to insert it, work in it, remove it, read it back. A
   test fails when `claudia_core.OBJECT_KINDS`, the `KINDS` table of `objects.cjs` and the `Examples` rows disagree
   (extend `tests/test_object_kinds_agree.py`, do not write a second one).
4. The steps the scenarios need and do not have: reload and open again; connection lost and back (use the server
   restart that `web/e2e/resilience.cjs` uses); page view and print preview; a second person (Ben, editor) and a reader
   (Cleo); the `#` list; screen-reader name (ARIA name and description); export to a format and import as a new
   document (O9).
5. Expect many reds: each is a bug entry (O4), sized, grouped by kind. Report the matrix of app × kind × scenario in
   the progress file (pass / bug id / pending).

**Acceptance:** WP1's known-list is empty; every (app, kind) row is collected; the matrix is in the progress file;
the CI specs job stays under 20 minutes (if not: shard with `pytest-xdist` by file, or ask).

### WP6: Gate G2, the owner's review (orchestrator)

Collect for the owner in one message: the reworded invariants (WP5.1), the review questions from WP4 and WP5, the WP7
drafts, and every bug found so far with its proposed size. Send a push notification, then wait. Nothing in WP7's step
code starts before the answers.

### WP7: New journeys, spec first (worker per app; drafts before G2, step code after)

Drafts follow `specs/README.md` ("How to write a scenario") and the matrix of the working agreement (states
empty/one/many/huge/error; actors one/two people/ai; operations create/edit/undo/delete/reload/export/import;
clients web in Firefox and GTK). Each draft comes with a `.review.md` that lists the edge cases with a proposed
default each, so the owner only vetoes.

Proposed journeys (O10, in this order):

1. **Import from disk round trip** (all apps): File ▸ Open ▸ Import from disk… with a docx/xlsx/pptx and an
   odt/ods/odp from `test-documents/`, edit, Download as the same format, import again, the edit is there.
2. **Save a checkpoint, look back, restore** (all apps): Save checkpoint… (Ctrl+S), a past entry previewed without
   changing the document, restore by an owner with the other editor's consent (the "suggest restore" flow), a reader
   cannot.
3. **The ai, act and suggest** (all apps): the switch above the dock tabs, a request in act mode changes the document
   at once and is undoable, in suggest mode the proposal is previewed and accepted or dropped. Needs a deterministic
   AI in E2E (see section 7, question Q4).
4. **App language** (all apps): Preferences ▸ App language ▸ Deutsch, the menus and dialogs show German, the choice
   survives a reload, the document's own language is untouched.
5. **computes:** enter numbers and a formula, it recalculates; insert and remove rows and columns by key; rename a
   sheet; new sheet; Random generator ▸ Generate… and Re-sample.
6. **creates:** new slide, text box with words, speaker notes, Present from beginning (F5) and back, Grid on and off.

**Acceptance (drafts):** each file plus its `.review.md` handed to G2. **Acceptance (after G2):** approved scenarios
bound, each either passing or tagged `@pending:<BUG-ID>`; WP1's test green.

### WP8: Integration and report (orchestrator, plus a fresh reviewer)

1. Merge `main`; run `scripts/check_debt.py --ci`, `./run-e2e.sh all --browser both`; CI green on the branch.
2. A fresh reviewer runs `/code-review` over the whole branch against this plan; fix what it finds.
3. Write the implementation note (`implementation-notes/`), the decision-log entries (D1450 on), the updated specs,
   and the report in the project's "done" format, including the before/after table of WP0 and every bug with its size.
4. Merge your own updates of `claudiaoffice-log` into the `backlog` branch.
5. Gate G3: the owner accepts; then the merge to `main`, push, and CI as the project instructions say.

---

## 6. Prompt skeleton for a worker

> You are a worker in the E2E rework of Claudia. Read `claudiaoffice-log/notes/e2e-rework-plan.md` sections 0, 2
> (with the owner's answers in `notes/e2e-rework-progress.md`), 3, 4 and your work package **WP<n>** only. You own
> exactly these files: <list from section 4>. Work in your own worktree from `e2e-rework` @ <commit>. Test first. You
> may not change the words of any approved scenario, weaken any assertion, or add a skip/xfail/`@needs-decision` to
> hide a failure; a failing scenario that shows a product bug gets a bug note (what, where, size 1–3) and stays red.
> Stop and report instead of guessing when you need a file you do not own or a decision this plan does not cover.
> Return: a patch against `e2e-rework`, and a note with what changed, the commands you ran and their counts before
> and after, what you could not run, bugs found, assumptions.

## 7. Open questions this plan cannot answer alone

- **Q1:** The `architecture-improvements` branch (D1430–D1449, E1.18 renames) is open; its renames may touch the same
  words and selectors. Should it land first, or should this run merge it in as it goes?
- **Q2:** The menu rebuild to workbook version 5 is pending; guardrail 9 keeps steps safe, but should WP7 drafts use
  today's menu words or the workbook's?
- **Q3:** Real-world documents for the import journey: are those in `test-documents/` enough, or will the owner supply
  more (offered on 2026-11-11)?
- **Q4:** E2E servers start with no language model. `claudia_ai.testing.FakeModel` exists for unit tests; journey 3
  needs a server flag to run with a scripted model. That is a small test hook in product code: allowed under O5 or
  not?
- **Q5:** Is a nightly Firefox run with a red result acceptable for a while, or must every Firefox bug be fixed before
  G3?
