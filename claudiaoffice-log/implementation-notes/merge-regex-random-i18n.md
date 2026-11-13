# Implementation notes: bringing regex-builder, random-in-computes and i18n onto main (2026-11-13)

Four feature branches had been worked on in parallel; this note says what the merge onto `main` (at `fd4b087`, "BITV
quick fixes") decided, so nobody has to rediscover it from the diffs.

## What came in, in which order

1. **`lists-and-anchors-in-compose`**: nothing to do. Its one commit is already on `main` as `95aa812`, applied onto a
   newer base; a plain `git merge` of the branch would even add `SetListItem` a second time to
   `tests/api/claudia_composes.json`. The branch is merged with `-s ours` (or deleted).
2. **`regex-builder`** (two commits), first, because it was the oldest base and its versions come first.
3. **`random-in-computes`**: the commit on GitHub, then the three that existed only on the owner's machine (web UI,
   the fix for the grid that threw in setup, outcome inputs named by their named range). The local and the GitHub
   branch could not be reconciled because the first commit was in both with different hashes but identical content.
4. **`i18n`**, last, because it touches the most files and sets rules (D320–D323) the new code then had to follow.

## Decisions taken at the merge

- **Decision numbers.** D291–D299 had been handed to four branches (`random-in-computes`, `i18n`, `presenter`,
  `worker-pool`). `random-in-computes` keeps them (nine decisions, cited in many places); `i18n`'s four became
  **D320–D323** in a new block D320–D339 (`ranges.md`). `presenter` and `worker-pool` still carry D291–D299 and need
  their own blocks before they are merged.
- **Versions.** Two branches claimed the same number twice: `regex-builder` took claudia-core 0.17.0, which `main`
  already had for page setup, and `i18n` took claudia-computes 0.4.0, which `random-in-computes` had. Core is now
  **0.18.0** (lists, which were "Unreleased" on `main`, and the search engine); computes is **0.4.0** (random,
  alternatives, following) then **0.5.0** (function catalog in other languages, outcome inputs named by their name).
- **The new code follows the i18n rules.** Menu labels of search and random are Title Case (D321) and match the GTK
  manifest, which already had them so ("Search & Replace…", "Random Generator…", "Resample Random Numbers",
  "Outcomes of This Cell…", "Follow Computation", "Stop Following"); shortcut labels are getters around `t()`; the
  server's search, random and trace messages go through `msg()` (D322); the help topic "searching-and-replacing" has
  a German file. Every msgid is translated (1451).

## Things found and fixed on the way

- `msg("… at most {limit} characters", max_text=…)` in `set_cells` and `define_sql` (from `i18n`): the template
  and the keyword disagreed, so `Message` raised `KeyError` and a too-long input got an internal error instead of
  `bad_request`. Both pass `limit=` now.
- `SheetGrid.vue` imported `useI18n` twice and declared `t` twice (once from the random UI, once from `i18n`).
- The page language (BITV, `setPageLanguage`) is declared again when the same language is chosen once more, now that
  the language is one shared state for the whole page; the two BITV tests start from English as a page does.
- Esc does not stop following a computation while the search panel is open (the panel takes Esc first).

## Checked

`scripts/check_debt.py` (ruff, format, mypy, vulture, catalogs, every Python test, coverage, Sphinx, perf guards, npm
audit, layout, web lint, vitest, vue-tsc, Linux client), `tests/e2e` (three greetings and the computes grid), and the
browser scripts CI runs plus `search`, `lists` and `regions`.
