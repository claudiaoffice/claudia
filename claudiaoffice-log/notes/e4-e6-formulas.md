# Formulas in claudia computes — E4.1, E4.2, E4.7, E6.1 in part

Written 2026-11-03; moved here 2026-11-05. The kernel was not changed. The decisions below are **proposals** for the
decision log; none has a D-number yet, and recording them is what closes E6.4.

> **Correction, 2026-11-05.** The last section of the original note described point-and-click cell references for E6.3
> as built, with `web/app/lib/pointing.ts`, 22 vitest cases and a nine-case browser scenario. **None of it existed in
> the repository or in any commit on any branch** at the time (PROC-03): the patch had not been pushed. **Rebuilt and
> verified 2026-11-06** (see "Point-and-click references" below) — same files, same counts, now in the tree.

## What exists

| Part | Where (`claudia_computes/`) | Notes |
|---|---|---|
| Tokenizer, Pratt parser, AST, printer | `formula/syntax.py`, `nodes.py`, `printer.py` | A formula is stored as canonical printed text (`{"t":"formula","v":"=SUM(A1:A3)"}`), so replay, snapshot and live state agree. Limit 8192 characters |
| Compiler | `formula/compiler.py` | AST to closures, chain flattening (`a+b+c+…` without recursion), constant folding, dispatch by node class |
| Core: operators | `formula/operators.py` | `+ - * / ^ & % = <> < <= > >=`, unary minus and plus |
| Core: forms | `formula/forms/` | IF, IFS, IFERROR, IFNA, CHOOSE, SWITCH, IS\*, ROW, COLUMN, ROWS, COLUMNS, INDEX, OFFSET, INDIRECT, MATCH, XMATCH, XLOOKUP, VLOOKUP, HLOOKUP. Lazy arguments, `Range` references, per-column lookup indexes (capped) |
| UserFunctions | `functions/library/` (69) | Everything that takes ranges and gives a value: SUM, PRODUCT, AVERAGE, MIN, MAX, COUNT\*, MEDIAN, VAR\*, STDEV\*, LARGE, SMALL, SUMPRODUCT, COUNTIF(S), SUMIF(S), AVERAGEIF(S), MAXIFS, MINIFS, and the number, logic and text families. A class joins the library with `@builtin` |
| Contract | `functions/base.py` | A description and at least one `Example` are mandatory, checked by `check_examples` in the tests. Arguments are converted by the type hints of `call()` |
| Calculator | `calc.py` | Incremental. A dependency index of single cells plus ranges filed by 256-row blocks per column, and a list for very wide ranges. Pull-based depth-first with its own stack. Cycles become `#CIRC!` for every cell on the cycle. OFFSET and INDIRECT are dynamic: always rechecked, with their reads recorded |
| Model and commands | `model.py`, `commands.py` | `SetCells` stores constants and formulas; values are calculated in `settle`. `Structure` and `RemoveSheet` rewrite formulas and return exact inverses |
| Server and web | `claudia-server` `computes.py`, `standin.py`; `web/app/lib/cells.ts` | `cells` returns `{t, v, f, d}`; error cells in rose; the formula bar shows the formula text. The stand-in AI writes `=SUM(…)` |

## Proposed decisions

1. **Where functions live.** Operators and everything that chooses what to evaluate, or needs to know *where* a
   reference points, are core forms. Everything that takes ranges and returns a value is a `UserFunction`, including
   SUMIF-style functions.
2. **Stored form.** A formula cell is stored as canonical text, not as the typed text and not as an AST. Typing
   `= a1 + b1` stores `=A1+B1`.
3. **Numbers (E6.4).** Whole numbers are exact up to 2^53 and become floats beyond; `/` gives floats; text is never
   coerced, so `="3"+2` is `#VALUE!`; TRUE/FALSE are 1/0 in arithmetic. Sums of floats use `math.fsum`, so the order
   of the sparse grid cannot change the result. Rounding goes through `Decimal(repr(x))`.
4. **A multi-cell result is `#VALUE!`** until spill exists.
5. **Structure edits** rewrite every affected formula, and whole-column or whole-row references stay whole (`A:A`
   stays `A:A` when a row is inserted at the top). References to a deleted cell or sheet become `#REF!`; undo restores
   the old text exactly.

## Measured

- Parse about 25 µs (simple), 59 µs (complex). Paste about 90 µs per formula. Open snapshot and structure edit about
  100 µs per formula.
- One edit in a 50k-row workbook with range readers: about 0.25 ms — **16.7 ms before the block index**.
- A 20k-deep chain: about 0.3 s.
- **Inserting a row in a workbook of 100k formulas: about 12 s**, because everything is rewritten and recalculated.
- Guards: `tests/test_formula_performance.py`, six scaling tests, run by the gate next to the core's.

## Known limits and follow-ups

- Spill and array results (E4.6) not built. No dates, no names (E6.5), no RANDOM.
- **Structure edits are not incremental**: they rewrite and recalculate everything (PERF-07). Follow-up: rewrite only
  formulas that refer to the edited sheet, and move cells without recompiling.
- No early cutoff: a formula whose result did not change still dirties its dependents.
- `SetCells.shifted_by` (a colleague's structure edit passing the author's undo) does not follow formulas that contain
  a sheet-qualified reference, because commands do not know sheet names.
- Copy and paste do not adjust relative references yet. `rewrite.shifted` exists and is tested, but nothing calls it
  from the paste path (E6.7).
- `requirements()` of a UserFunction is not implemented; the function folder belongs to a later epic (E4.10).
- The function registry is process-wide; a formula compiled before its function is registered shows `#NAME?` until it
  is recompiled.

## Point-and-click references (E6.3) — built, verified 2026-11-06

Described in the original note as built on 2026-11-03; it was in no commit (PROC-03). Rebuilt from the specification
below and now in the tree at `13d1c80`: `web/app/lib/pointing.ts` (107 lines), 22 cases in `web/tests/pointing.test.ts`
and the nine-case browser scenario `web/e2e/pointing.cjs` (`npm run e2e:pointing`), matching the original note's
counts exactly. Kept as the specification below, which the implementation follows.

While a formula is typed, a click or drag on the grid should write the picked cells into it instead of ending the
edit, for any argument.

- **Where a pick may go:** after a character that expects a value (`=`, `(`, `,`, an operator, a comparison), where it
  is *inserted*; directly after a reference, where it *replaces* that reference, so a second click or a drag moving on
  replaces the first pick. Nowhere inside a text, after a name, a number, `)` or `%`, or directly in front of a name —
  there a click ends the edit as before.
- **Written as** `B2`, `B2:C5` from any corner, `B:B` for a whole column from a header click, `3:4` for whole rows,
  and `Name!` or `'My sheet'!` in front when the pick is on another sheet, quoted as the server writes it. The whole
  sheet is not picked.
- **The focus stays in the text** (formula bar or cell editor, whichever the person was typing in) and the caret goes
  behind the pick, so typing `)` or `,` continues at once; text after the caret is kept (`=SUM(|)+1`).
- **Another sheet:** a sheet tab can be clicked while pointing; the edit remembers its own sheet and Enter returns to
  it. If no reference fits at the caret, the tab click ends the edit first.
- **Seen:** the picked range is dashed; every reference of the formula being edited is outlined in the grid in the
  colour of its order; the formula bar shows the same text.
- **Side fixes that went with it:** picking a whole column must not scroll the grid to the last row; the presence
  update must not be sent while editing, because it clashes with the cell lock.
- **Not in scope:** arrow keys do not start pointing, no F4 to toggle `$`, no dragging of the outline to change a
  reference, and shift+click extends only a pick made with the mouse.

## Gates

The gate was clean when this was written: ruff, mypy and vulture; Sphinx with warnings as errors (the formula API was
added to `docs/api/apps.rst`); the perf guards; web tests and `vue-tsc`. vulture ignores the decorators `@form` and
`@builtin`, which register a function in a table so nothing calls it by name.
