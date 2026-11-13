# Search & replace in computes: engine, workbook layer, server methods, panel (E1.12, E5.15, E6.20; D281–D286)

Built 2026-11-13 on `regex-builder`, from the agreed screens in `notes/search-and-replace.md` and `notes/mockups/`.
This note is what the code does and why it is shaped so; the design is in the note of the same name under `notes/`.

## Three layers, one meaning of a search

| Layer | Where | Knows about |
|---|---|---|
| Engine | `claudia_core.search` | patterns, builder models, spans, kept parts; nothing of any app |
| Workbook | `claudia_computes.search` | which texts a sheet has (text, formulas, values), locks, formula parsing, the replace plan |
| Protocol | `claudia_server.computes`: `search_find`, `search_preview`, `search_replace` | requests, scopes, revisions, the wire shapes |

The client (`web/app/lib/search.ts`) holds the *model* the person edits and the *sentence* that restates it; it never
evaluates a pattern. The panel (`SearchPanel.vue`) is one component; an app gives it a `SearchHost`
(`web/app/lib/sheet-search-host.ts` for computes) that says which scopes and kinds exist, how to name a match
(`Costs!B2`) and how to go to it.

## The engine

Three query modes share one answer shape: `text` (the quick field: what is typed is what is found, escaped), `builder`
(parts, counts, kept names, conditions, `combine`, `whole`) and `pattern` (find, filter, replace; her own syntax).
Python `re`, DOTALL, ignore case unless `match_case`. A builder part is compiled to a pattern fragment; "a letter" is
`[^\W\d_]` because `re` has no `\p{L}`.

Because `re` cannot be interrupted, a search is kept finite in three ways (D284 as built):

1. a **static guard** (on the parsed pattern) refuses a repeat whose body starts with a repeat or has branches that can
   match the same text (`(a+)+$`, `((a|a)|c)+`, `(?:a+|b)+$`, …), also inside look-aheads, and a pattern nested too
   deep, before it runs; the answer is an `error` that says why, never a hung server;
2. **size caps** on what is asked: `MAX_PATTERN_CHARS` 2000, `MAX_TEXT_CHARS` 1000 per text or replacement literal,
   `MAX_PARTS` 30, `MAX_CONDITIONS` 10, `MAX_REPLACEMENT_ITEMS` 50, `MAX_SET_CHARS` 200, `MAX_COUNT` 1000;
3. a **time budget** (`SEARCH_SECONDS` 2.0 in `claudia_server.computes`), checked between texts; when it runs out the answer
   has `timed_out: true` and the panel says the list may be incomplete.

A pattern that cannot run is answered as `error: {message, field, position}` (the request itself succeeds), so a
client can explain it while the person types. The panel turns the message into a sentence (`explainError`) with a
**1-based** character position.

A condition on the cell (`contains`, `not_contains`, `starts_with`, `ends_with`, `is`, `contains_any_of`,
`not_contains_any_of`) has the wire shape `{kind, text}` or `{kind, chars}`. A cell that has a match but fails a
condition is **left out**, with the failing condition as the reason, and listed under “Left out (n)”.

## The workbook layer

Texts come in three kinds, from one pass over the sheet: `text` (text constants), `formulas` (the formula as typed,
with `=`) and `values` (numbers, booleans, formula results, spilled cells). `values` is find-only; the Values switch
shows a lock while Replace is open (D285).

**Replace is a plan, then a `Batch`.** `plan_replacement` returns `Change`s and `Skip`s; `replace_command` turns the
changes into one `Batch(name="Replace in N cell(s)")` of `SetCells` holding the *final* cell contents. It stores what
was made, not the pattern, so replay, Undo (D54) and the history list need nothing new (D286 as built; the proposal's
`ReplaceInCells` command was not needed). A cell is skipped, and named, for one of:

* `locked`: someone else holds it. `presence.conflicts(owner, regions)` is asked once per sheet with a whole-sheet
  `CellRegion`; one held cell never refuses the rest;
* `formula`: the replacement would leave something that does not parse (`parse_formula(text, sheet_ids).ast is None`);
  the formula separator is `,`;
* `too_long`: the result is longer than a cell may be.

`MAX_REPLACED_CELLS` is 10 000 per request; `MAX_PREVIEWED` 2 000 changes are sent back by the preview; `MAX_LISTED`
2 000 matches by a find (`truncated` says so). `Hit` carries `clipped_before`/`clipped_after` so the panel can put an
ellipsis where an excerpt of a long cell was cut.

The computes-only builder part `cellref` (`EXTRA_PARTS`) matches `A1` and `$B$2` style references without matching
function names (`LOG10(`) or words that merely end in digits.

## The panel

State is one reactive `SearchModel`; the query sent is `toQuery(model, {replace})`. Typing is debounced (150 ms) and
run through `latest()`, so only the newest answer is used and a failure leaves what was showing. The document
revision is watched, so an edit by anyone re-runs a showing search.

* Opening Replace sets the kinds to Text only and locks Values; a pattern that is also in formulas says so
  (“appears in 4 formulas, which are left alone”).
* Each match has a tick; unticked ones are sent as `leave`. “Replace this one” leaves every other match; “Replace all
  N” uses the preview's own total, so the button says what will happen.
* The grid draws `marksFor(...)`: a band and an underline on a matching cell (never colour alone), a corner for a
  match inside a formula, a heavier frame for the one being looked at, a hatched lock for a cell the replacement
  skips, and the replacement's new text in place of the old while the preview is open.
* A typed pattern is reached through ⋯ ▸ “Write the pattern yourself…”, starting from the pattern the builder made
  (`answer.pattern`). “Back to the builder” restores a snapshot after a confirmation. The words “regular expression”
  and “regex” appear nowhere on the surface; the typed view says only “Pattern syntax: Python re”. (`e2e/search.cjs`
  checks that.)
* The aria-live line is “N matches in M cells”; every control has a label; the panel closes with Esc and the focus
  goes back to the grid.

## Menu, shortcuts, desktop clients

`searchItem()` in `document-menus.ts` is the one `edit.search-replace` item (label “Search & replace…”, hint Ctrl+F);
`searchShortcuts()` gives Ctrl+F and Ctrl+H, the latter enabled only when replacing is allowed. Both go through the
shared shortcut rule, so neither fires while a text field has the focus. The GTK manifest has a page action
`edit.search-replace` with `<Primary>f` after the clipboard block; Windows and macOS menus are regenerated from it
(`clients/*/tools/generate_menu.py --all`). The desktop shells frame the web page, which owns the panel, so nothing
else changes in them.

## Not built yet

* Hosts for composes (E9.28) and creates (E10.19): the Edit entry is only in computes for now; `searchItem` is shared.
* “Select the cells” of the mock-up: a selection is one rectangle, scattered matches cannot be selected.
* The sample text for a typed pattern (D283).
* Virtualised list: the first 200 rows and “Show more”.
* The Help topic (`computes.searching-and-replacing`) opens the How-do-I section of the Help tab, not the topic itself.
* A test that drives `search_replace` through the assistant (it is registered as a model method).

## Numbers

Core 0.17.0, computes 0.3.1, server changelog Unreleased (version unchanged: `__all__` did not change),
`PROTOCOL_VERSION` 2. Web: 736 tests. Coverage floors ratcheted with `scripts/check_coverage.py --ratchet`.
