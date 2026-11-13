# Random numbers, alternatives and following a computation in computes (E6.21–E6.23, D291–D299)

Branch `random-in-computes`. Three features that share one idea: a workbook is a function of inputs, and the user
learns by changing them. The screens are `notes/mockups/computes-alternatives-*.svg`, `computes-random-*.svg`,
`computes-follow-computation-*.svg` and `computes-random-alternatives-follow-menus.svg`; the owner approved them on
2026-11-13 with one change: no arrows between connected cells, only lit cells (D297).

## What was built

**`claudia-computes` 0.4.0**
* `draws.py`: `draw(seed, sheet, row, col, call, index, draw)` → a uniform number in (0, 1) from BLAKE2b of the
  position, never from a clock (D291). `commands.py`: `Resample` (relative, its inverse is the opposite sign) and
  `SetRandomSeed`; `events.py`: `RandomChanged`; the workbook state is schema 8 (`random: {seed, draw}`).
* `distributions.py` and `special.py`: every distribution is a quantile function of that one uniform number (D293);
  `formula/forms/random.py`: `RAND`, `RANDBETWEEN`, `RANDOM("dist", …)` with optional low/high cut.
* `alternatives.py`, `formula/forms/alternatives.py`: `{a, b, c}` is typed in as `=ALTERNATIVES(a,b,c)`, or
  `=SCENARIOS("name", …)`; only a top-level call is an input (D294). `Compiled.alternatives`, `Scope.choice`.
* `outcomes.py`: components of inputs and their downstream closure; the calculator's round is run once per
  combination with `calc.choice` set; summaries are refreshed in `settle`/`recalculate_all` for stale components only
  (D295). `OutcomeTable`, sensitivity and the paired mode (D296). `Sheet.alternatives` and `Sheet.outcomes` are
  derived state, mirrored by diffing old and new keys so `CellsChanged` reports them.
* `trace.py`: breadth-first over precedents and `calc.readers_of`; the roles are computed on the whole connected set
  and only the list is cut to the window (D297).

**`claudia-computes-io` 0.3.0**: `extensions.py` writes and reads the Excel / OpenFormula text of `RANDOM` and the
alternatives note; `xlsx.py`, `ods.py` call it; `xlsx_export_losses` is new (D292, D298, D299).

**`claudia-server`**: `random_state`, `resample`, `set_random_seed`, `outcome_table`, `trace`; `cells` carries `alts`
and `out`; `export_office` answers `losses` for xlsx. `PROTOCOL_VERSION` stays 2: methods and fields were added, none
changed.

## How it was checked

Tests first for each layer (core 14 + 31 + the earlier random tests, io three files, server ten tests). The Excel
formulas were checked three ways: a test-only evaluator of the exported text against the model's own quantiles, a real
LibreOffice conversion of an xlsx and of an ods (values in plausible ranges), and the round trip back to `RANDOM`.
`scripts/check_debt.py --fast`: ruff, mypy, vulture, i18n, API snapshot and coverage floors are green; the tests pass
except the two checks about the decision log, which are green once D291–D299 exist, and a pre-existing failure in
`tests/test_notes_claim_built_files.py` (`notes/e9-print-and-layout.md` names `web/public/wasm`, a build output that is
not in a checkout).

## Things that were found on the way

* A formula with a literal discrete list cannot be written with Excel's array constants and still be parsed by
  claudia's own formula parser, so the generated Excel text is embedded as verbatim name nodes and the outer
  parentheses are stripped when it is the whole formula.
* An unnamed alternative must have a label that reparses: `alt N`, not the bare number.
* uniform, exponential, weibull and pert are written as arithmetic on `RAND()`, so they come back as arithmetic, not
  as `RANDOM(...)`: the file has no way to say which one it was.

## Not done, and said so

* **No client yet.** The web app (Nuxt) has no chips, dot strips, outcome pop-over, Random generator dialog, Tools
  entries, F9 or following; the GTK client and the neutralino clients have no counterpart. Every menu entry needs a key
  shortcut, a .po label and the BITV checks when they are made; the server methods above are what they call.
* triangular, poisson and a non-literal discrete list are written to Excel as their current value (a `formula` /
  `random` loss).
* Readers that find their cells dynamically (OFFSET, INDIRECT) are not followed by the outcomes; an alternative that is
  a formula is evaluated with the other inputs' current choices.
* No `Simulate()` (the owner's call, 2026-11-13).
* The help text of the new functions comes from their docstrings; the menus and dialogs have none yet.
