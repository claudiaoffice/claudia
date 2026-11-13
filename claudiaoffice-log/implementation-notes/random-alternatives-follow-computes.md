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

## The clients (second patch)

* **Web** (`web/app`): `lib/outcomes.ts`, `lib/follow.ts`, `lib/random-generator.ts` are plain TypeScript with
  tests; `Session` has `resample`, `setRandomSeed`, `randomPreview`, `outcomeTable`, `follow`/`unfollow` and keeps
  `state.random` and `state.trace` current (a followed cell is asked for again, once, when cells, structure or
  sheets change). `SheetGrid.vue` draws chips, "≈ median" with the dot strip, lit cells (shape + left bar + tint, so
  not by colour alone) and dimmed cells; `OutcomePopover.vue`, `RandomDialog.vue`, `FollowPill.vue` are new;
  `FooterBar.vue` marks tabs the connection continues on; `Workspace.vue` has the Tools entries (Ctrl+Alt+R random
  generator, F9 resample, Ctrl+Alt+O outcomes, Ctrl+Alt+F follow; by physical key `code`), the cell menu and Esc.
* **Follow tracks the selection**: while following is on, selecting another cell follows that one, so the lights move
  with the cursor; the window asked from the server is the view plus one screen on each side and is asked again only
  when the view leaves it. This is a reading of "click a cell" in the owner's request and is to be confirmed.
* **A cell menu** (right click on a cell) is new; until now only headers had one. It carries the clipboard entries,
  Outcomes, Follow and Resample as in the menus mock. Right-clicking a cell no longer opens the browser's own menu.
* **Desktop**: the Linux manifest has the four entries with accelerators (Follow is checkable); the macOS and Windows
  menu JSON is regenerated from it. The shells show this web page, so the drawing needs nothing of their own.
* **i18n**: 100 German strings in `po/de.po`, `claudia.mo` compiled.

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

* **Browser check.** The first UI patch threw in `SheetGrid.vue`'s setup (a `watch` on `range` read `resizeDrag`, a
  `const` declared further down) and the page showed the history and chat panel over the whole window. vitest cannot
  see that (it only reaches `web/app/lib`), so `tests/e2e/test_computes_grid.py` now opens a document in a real
  browser, types alternatives, follows a computation and uses the Random generator, and fails on any page error.
  Looked at by eye in headless Chrome: chips, median with dots, lit and dimmed cells, the pill, the outcomes popover,
  the cell menu, the generator. Not yet looked at: dark mode, the tab marker for other sheets, narrow windows.
* **Outcomes of a RANDOM cell** is not offered: the server only summarises results of alternatives (`out`), so the
  menu entry is greyed on a cell that depends on `RANDOM()` alone (the mock enables it there).
* **Pin as chart** (outcome pop-over, mock 1) is not built. The footer line "Random draw N · seed" is not built; the
  draw number is on the "Draw N" button next to the formula bar. The typing hint under the cell while `{…}` is typed
  has its logic (`typingHint` in `web/app/lib/outcomes.ts`) but is not drawn.
* triangular, poisson and a non-literal discrete list are written to Excel as their current value (a `formula` /
  `random` loss).
* Readers that find their cells dynamically (OFFSET, INDIRECT) are not followed by the outcomes; an alternative that is
  a formula is evaluated with the other inputs' current choices.
* No `Simulate()` (the owner's call, 2026-11-13).
* The help text of the new functions comes from their docstrings; the menus and dialogs have none yet.
