# Implementation note: bug eater, batch 3

Written 2026-11-25, branch `batch-3` (from `main` after batch 2 was merged). The brief is `notes/bug-eater.md`. The
owner asked for UX-85 and every bug found in batch 2 to be fixed here, and approved the Gherkin of UX-84. UX-69 stays
out (the menus are to be worked on with the owner). No decision of its own; the next free id is D2004. One commit per
item, its message starting with the item's ID.

## What changed, per item

| Item | Change | Test written first (seen red) |
|---|---|---|
| UX-85 | `name_and_describe` describes every object with `DescribeObject`; a table gets words, never the decoration tick | `test_server_thing_names.py::test_a_table_is_named_and_described_and_one_undo_takes_both_back` (refused with the developer sentence), and the composes invariant, no longer `@pending` |
| UX-89 | A table is labelled by its tab (`aria-labelledby`) and described by its description (`aria-describedby`), not named by its whole caption with "Options…" | the invariant's step now asks for the exact name and the description; it read "Table 1 — … Options…" |
| UX-84 | The approved scenario "What I have selected, a colleague sees in my colour with my name, and cannot change", for a text, a workbook and a presentation | the scenario (written after the fix of batch 2; it passes in Chromium) |
| PROC-60 | The eight waits that gave `wait_for_function` a bare expression wait for a locator or give a function | `tests/test_e2e_waits.py` (a guard reading the browser tests); the failure was measured against a page served with `script-src 'self'` |
| PROC-59 | The specs ask only that the web app is built (`test_greeting.NOT_BUILT`); the browser fixture starts the browser the run asked for. On CI a pytest run in which no test passed fails | `tests/test_run_e2e.py` (two tests: on CI, on a computer) |
| UX-86 | A colleague's name tag on a cell outline or an object goes inside the box's top edge where above it would be under the column letters, and stays at the area's top for a box scrolled partly out of it (`lib/name-tag.ts`) | `web/tests/name-tag.test.ts` |
| UX-88 | A `role=status` region that is always on the page says the notice: emptied, then filled 100 ms later, so the same words twice are said twice; the visible toast is `aria-hidden` (`lib/notice-said.ts`) | `web/tests/notice-said.test.ts` |
| CODE-98 | `BaseSession.tellLookOnly()` in 21 places; no other file says the sentence | `web/tests/look-only.test.ts` (with a guard over `web/app`) |
| UX-87 | `DocumentModel.setup_commands(language, *, translate=None)`: the server passes its catalogue, and a new workbook's first sheet is "Blatt1" for a German person, "Sheet1" in English or without a catalogue | `test_server_setup.py`, `test_computes_thing_names.py` |
| PROC-61 | The chain guard counts the Python lines and loop turns of a calculation (`work_of`, `sys.monitoring`, in the test only) instead of timing it: a 10x chain is 9.96x the work on every machine; the bound is 15 | a guard that reads the clock fails; a quadratic stand-in is caught at 49x |

**Versions:** the setup hook gains a keyword with a default in claudia-core, -computes, -composes and -creates (an
addition, under *Unreleased* in their changelogs; API snapshots regenerated; the versions are raised at release, as
the repository does).

## Assumptions

- UX-87: a language without a catalogue on the server (any but German today) gets "Sheet1", though the web has a
  pseudo-locale. An export of a workbook with no sheets still writes a "Sheet1" of its own (`ods.py`, `xlsx.py`).
- UX-88: 100 ms is long enough for a screen reader to notice two changes. The new region has no `aria-live` beyond its
  role, because `grid-a11y.cjs` finds the grid's own region by `[role=status][aria-live=polite]`.
- UX-86: the room is measured from the top of the sheet area as shown, after scrolling.
- PROC-61: counting does not see work done in C (a deletion at the front of a list, `x in list`, `sorted`). The known
  case is PERF-13, which the old timing guard saw in part and the new one does not. The other timing guards of
  `test_formula_performance.py` are unchanged (none has been seen failing).

## Found in this batch

- PROC-59 was fixed in batch 2 only on paper: the first Firefox job on `main` was green with "71 skipped".
- UX-90: about 25 other `role=status` elements appear with their text (BITV 4.1.3).
- PERF-13: calculating a chain is quadratic in `Waiting.done`.
- On `main`: the stand-in for LibreOffice in PROC-22's test was a shell script, which failed on Windows (fixed on
  `main`, `7a840356`); CODE-96 was given twice the same day (the look-only item is CODE-98 now, `01bde500`).

## Say what could not be run

- Firefox here (it cannot be downloaded); the Firefox job on CI is the check, now that it runs.
- A screen reader (UX-88, UX-89 are checked through the accessibility tree only).
- The desktop clients by hand; they load the web app.
