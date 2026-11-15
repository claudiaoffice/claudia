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

* ~~Hosts for composes (E9.28) and creates (E10.19)~~: built 2026-11-14, see the last section.
* “Select the cells” of the mock-up: a selection is one rectangle, scattered matches cannot be selected.
* The sample text for a typed pattern (D283).
* Virtualised list: the first 200 rows and “Show more”.
* ~~The Help topic opens the How-do-I section, not the topic itself~~: built 2026-11-15, see the last section.
* A test that drives `search_replace` through the assistant (it is registered as a model method).

## Numbers

Core 0.17.0, computes 0.3.1, server changelog Unreleased (version unchanged: `__all__` did not change),
`PROTOCOL_VERSION` 2. Web: 736 tests. Coverage floors ratcheted with `scripts/check_coverage.py --ratchet`.

## 2026-11-13, after QA: `regex`, a package of its own, places as `at` (SEC-18, CODE-18, PERF-11; D288, D289)

* **Engine.** `claudia_core.search` moved to the new package `claudia-search` (`claudia_search.engine`), because the
  kernel imports the standard library only. Patterns are read by `re` (syntax and error messages unchanged; the
  client's `explainError` keeps working) and run by `regex` with a timeout: every `CompiledSearch` method takes a
  `deadline` (`time.monotonic()`), raises `SearchTimeout` when it passes, and without one a call may take
  `MAX_SECONDS` (1 s). The shape guard (`_backtracks` and friends) is gone, and with it the client's sentence for it.
  `_check_template` reads a replacement against a stand-in `re` pattern with the same groups, because `regex` reads a
  replacement only when it is used.
* **App-neutral search.** `claudia_search.scan` and `plan` run over `Text(at, kind, text)` and answer `Hit`, `LeftOut`,
  `Change`, `Skip`, all with `at` and a `to_data()` that is the wire shape; `plan` takes `leave` as `(at, number)` and
  a `refuse(text, after)` callback for the app's own rules. `location_key` keys a place whatever its field order.
* **Computes.** `claudia_computes.search` offers `workbook_texts`, `scan_workbook` (counts by `text`/`formulas`/`values`
  as before), `plan_replacement` and `replace_command` (which makes the cell contents; a plan no longer carries them),
  with `cell_at`/`cell_of` for the place.
* **Server.** The three methods moved to `claudia_server/computes_search.py` (CODE-21 in part), registered by
  `add_search_methods(computes_methods, workbook=_workbook)`. One deadline per request (`SEARCH_SECONDS`, 2 s) for
  find, preview and replace: preview answers `timed_out`, replace refuses. `leave` is `{at, match}`, at most 10000.
* **Web.** `SearchHost` lives in `lib/search.ts` and has `keyOf`, `where`, `jump` taking `at`, and `scopeLabel`; the
  cell labels, `cellOf`, and the grid marks (`marksFor`, `SearchMarks`) moved to `lib/sheet-search-host.ts`.
* **Not changed:** the panel's words still say "cell" and the kinds are computes'; they become the host's with E9.28.

## 2026-11-14: composes and creates (E9.28, E10.19; D470–D472)

Built on branch `search` on the three layers above, with the app-neutral parts pulled out so a fourth host would be
small.

* **Kernel.** `claudia_core.object_texts` (`object_texts`, `edit_object_text`, `ObjectText`) reads the words, shape
  label and description of an object and turns an edit of one into the command that makes it (`SetParagraph`,
  `DescribeObject`); `replace_spans` applies spans to a paragraph. Both apps use them, so an object's words are one
  thing in composes and creates.
* **Per app.** `claudia_composes.search` and `claudia_creates.search` offer their texts with places (`block_at`,
  `object_at`, `notes_at`), `plan_replacement` and `replace_command`. Composes derives the kind of a paragraph from
  its style chain (heading, remark, text), has the scopes section (from a heading of level 1 or 2) and range, and
  replaces by `DeleteText` + `InsertText` per edit from the end of the paragraph, so authorship runs outside the match
  stay and the replacer authors the new words. Creates replaces object words through `edit_object_text` and notes
  through `SetSlideNotes` (limit `MAX_NOTES_LENGTH`, 20 000).
* **Server.** `claudia_server.search_methods` is the generic `SearchApp` adapter and `add_search_methods`;
  `computes_search`, `composes_search` and `creates_search` are now thin adapters with their own docstrings, places,
  scopes and limits (`MAX_REPLACED_CELLS` / `MAX_REPLACED_TEXTS`). `leave` entries may carry `said`, the text the match
  had when it was shown; a mismatch skips the text as `changed`. Locks: composes asks `presence.conflicts` per edit
  span and skips the paragraph if any match is in a held zone (paragraph-level, D472); creates skips an object another
  person has selected.
* **Web.** `SearchHost` gained `unit`, `switches`, `scopes`, `extraParts`; the panel's switches, kind labels and
  sentences are static `t()` calls (the catalogue extractor reads only those) and the panel says "cell" or "text" by
  `unit`. `lib/text-search-host.ts` and `lib/slide-search-host.ts` are the hosts; `lib/use-search.ts` is the open/close
  state the two workspaces share; `searchFind`/`searchPreview`/`searchReplace` moved from the sheet session to
  `base-session.ts`. The editor draws `TextMark`s (band, underline, outline for the current match, `data-found`), the
  slide draws `SlideMark`s in the words of an object by cutting them with `piecesOf`.
* **Menus.** `searchItem` and `searchShortcuts` in the web; `_search_block(describe)` in the GTK manifest for all
  three apps, Windows and macOS regenerated.

**Numbers.** Core 0.23.0, composes 0.8.0, creates 0.11.0, search 0.2.0, server 0.34.0 (API snapshots regenerated);
creates coverage floor 95. Web: 1188 tests.

**Not built.** The assistant's `search_replace` model method for composes and creates (replace is people-only in
composes, D472); marks inside the notes field; an e2e script per app (`web/e2e/search.cjs` covers computes only);
a heading shown with each result in composes; per-match (instead of per-paragraph) lock skipping; the Windows and macOS
npm tests were not run here (no `node_modules`), only their menu generator's checks.

## 2026-11-15: the panel's quick path, moving, the help topic (branch `search-ui`; D520–D522; UX-39)

What the owner saw on the composes panel, and what changed.

* **The line of matches** is `matchSummary(count, units, unit, t)` in `lib/search.ts`: "No matches", "One match", "n matches"; only
  a sheet adds "in m cells", and only when m < n. A text or a slide never says "in x texts". The old wording is gone from
  the catalogue.
* **"Look in"** is one button (`data-testid="search-lookin"`) whose text is `lookInSummary(...)`: "Everything (n)", the
  names when one or two kinds are on, "k of n kinds", "Nothing". It opens a `Popover` with a checkbox per kind (the
  count, or 🔒 for a kind that cannot be replaced while Replace is open), and All / None. The kinds are still the
  host's `switches`, so a fourth app gets the list for free. "Match case" and "Whole text/cell" stay checkboxes;
  "Replace with… ›" and "Build a pattern…" are `.btn` buttons (the end-to-end script finds the first by its text, which is
  unchanged).
* **Where it sits.** `DocumentFrame` sets `--dock-width` (340px beside an open dock, 0 when the dock is closed or the
  window is narrow) and the panel's right edge is `16px + --dock-width`. The help it opens is therefore never under it.
* **Moving** (`lib/dragging.ts`, `lib/use-draggable.ts`; used by `Modal.vue` and `SearchPanel.vue`). The pure part decides
  where a box may be (`clampShift`: inside the window, a 48 px strip of the top edge always reachable; a box wider than
  the window can be moved across it), what a drag and what Alt+arrows do (`dragged`, `keyShift`: 20 px, 100 with Shift),
  what starts a drag (`startsDrag`: not a button, field or link in the header) and where Alt+arrows must be left alone
  (`takesTyping`). The wiring keeps one offset per dialog title in a `Map` for the life of the page and re-fits on resize.
  **The offset is applied through `--dx` and `--dy` on the insets, not a transform**: with `transform` the box becomes the
  containing block of the `position: fixed` popovers inside it (the Look-in list, the ⋯ menu, the dialogs' own pickers)
  and they open far from their button. `Modal.vue`'s backdrop click ignores the click that ends a drag
  (`justDragged()`), or a drag that ends outside would close the dialog; Esc is untouched (D128).
* **The help topic.** `SearchHost.helpTopic` (one id per app) goes `SearchPanel → @help → DocumentFrame.openHelp(mode, topic)
  → SidePanel.openHelp → HelpPanel.showTopic(id)`. `showTopic` opens the topic and focuses its heading; an unknown id shows the
  how-to list. The body is drawn by `NotesText` with `flow`: `lib/help-markdown.ts` joins soft line breaks (not inside code
  fences, not before a heading, a list item or a quote) and hands the text to `notes-markdown.ts`, so it is the notes' safe
  reader: no HTML. Function help (`<pre class="body">`) is still plain text.
* **Texts.** Five new strings in the catalogue ("All", "Everything ({count})", "Nothing", "{names} ({count})", "{count} of {total} kinds"; "None" existed, "{count} matches in {texts} texts" went),
  German in `po/de.po`. The three help topics were rewritten for the button and a "Moving the panel" section, with new
  `source-hash`es in the German files.

**Tested.** `dragging.test.ts` (clamping, drag arithmetic, keys, what starts a drag), `help-markdown.test.ts`,
`search-panel-wording.test.ts`, and `helpTopic` in the three hosts' tests; `modal-layout.test.ts` still passes. The
components themselves were driven in headless Chrome (the Look-in list, the layout beside an open and a closed dock,
dragging the panel and a dialog, the topic opening on its heading, Markdown drawn as headings and lists); that script is
not in the repository, and `web/e2e/search.cjs` was not changed or run here.

**Not built.** Positions kept across a reload; the Alt+arrow keys inside text fields (they keep the browser's meaning);
Markdown for function help; a drag handle on the *whole* of a dialog; an e2e script for moving (Playwright can do it:
`mouse.down` on the header, `mouse.move`, `mouse.up`, then compare `getBoundingClientRect()`); the
desktop clients need no change (they frame this page, and no menu entry was added).
