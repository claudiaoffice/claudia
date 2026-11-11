# Plan: the styling suite (branch `styling-suite`; D300–D315)

**The goal.** The style model of D300–D310 — facets, kinds, slots, purpose bundles, no direct formatting — is how
*everything* in claudia is styled: every kind of thing that can be styled declares its slots, the server offers
one style API for all three apps, and one style UI works on all of them. Styling computes cells is part of that
end state, not the point of it.

**The shape of the work.** Two steps, as the owner put it, plus a short finish:

1. **Re-model** — the new model in the kernel, composes and creates (and computes' floating objects) moved onto
   it, one style API on the server for all three apps, and cells given slots in the backend. *Nothing a person
   sees changes in step 1*, except that cells can be styled through the API.
2. **The new UI** — the shared components built against slots, then put into composes, creates and computes and
   the shells, and last the cell styling in the grid.
3. **Finish** — file formats, the AI user, accessibility, docs, and removing what the re-model left behind.

Each numbered sub-step below is one pull request into `styling-suite` (or a few, if it is large) with a *done when*,
and the gate at the end of this note passes before it merges. The *how* of the kernel and UI work is in
`implementation-notes-style-facets.md` (the "facets note"); this plan says what comes in which order and what is
done. Written against `styling-suite` at `19e1779` (2026-11-10).

## What can be styled, and its slots

The owner's list was image, shape, paragraph, text, text box, cell, diagram. Checked against the code
(`OBJECT_KINDS = ("text", "shape", "image", "diagram")` in `claudia_core/objects.py`, composes' blocks, creates'
slides, computes' sheets and chart tabs), the list of things that exist today is complete — "text" and
"paragraph" are one thing (a composes paragraph is a `Paragraph`, the same entity as the words in a text box,
D181). Missing from the list are only things that **have no style at all today**: a creates **slide** (its
background), a composes **page**, the **parts of a diagram** (its titles, axes and series colours), and a computes
**chart tab** (it only shows a diagram and adds nothing of its own). They are listed so that the slot table has a
place for them; none is built in this round, but the architecture must take them later by adding a row (D315).

| Thing | Where it lives | Slot | Reads facets | Kind offered | Today |
|---|---|---|---|---|---|
| **paragraph** (composes) | `TextModel.blocks[i].style` | paragraph | Box, Paragraph, Text | `paragraph` | one style, all facets mixed |
| **text box** (all three) | `ObjectBody.style` | box | Box | `box` | points at `body-text` (a words style) |
| | `ObjectBody.paragraph.style` | words | Paragraph, Text | `paragraph` | starts as the object's own style |
| **shape** (all three) | `ObjectBody.style` | outline | Outline | `outline` | `plain-shape`, mixes outline and words |
| | `ObjectBody.paragraph.style` | label | Paragraph, Text | `paragraph` | as for a text box |
| **image** (all three) | `ObjectBody.style` | box | nothing yet (a picture carries its own colours; a border later) | `box` | `plain-image`, empty |
| **diagram** (all three; a chart) | `ObjectBody.style` | box | Box | `box` | box only (D209) |
| **cell** (computes) | style ranges per sheet (new) | box | Box | `box` | nothing |
| | style ranges per sheet (new) | words | Paragraph, Text | `paragraph` | nothing |
| *later (D315):* slide, page, diagram parts, chart tab | — | — | — | — | no style |

Rules the table follows: a slot reads only its facets (D304); one style per slot, no direct formatting (D306); a
style applied to a thing with two slots fills both with the one bundle, and "only the box" deviates one slot
(D309, and D311 for cells); a style is offered only where its kind fits (D305); the kinds are `paragraph`, `box`
and `outline` (D312).

## Step 0 — decided (2026-11-10)

The owner's answers are in the log: cells fill both slots (D311); the kinds are `paragraph | box | outline` (D312,
and the facets note is corrected); the five built-in cell styles (D313); **no xlsx for cell styles in this round**
(D314, later as E6.18); the slot table is open for slide, page, diagram parts and chart tab later (D315); GTK opens
the popover like Windows and macOS (D301). Nothing is left to decide before step 1.

The **mock-ups** that step 2 needs (computes cells, and the editor of a thing with two slots) are drawn during
step 1: they are needed at 2.1, and step 1 changes nothing on screen.

---

## Step 1 — re-model: one style system in the backend of all three apps

**Done when (whole step):** all three apps look and behave exactly as before in a browser — same documents, same
menus, same dialogs — while underneath every style has a kind, every styled thing declares its slots, all style
writes go through one server API, and cells can be styled through that API. A document from before the step does
not open (D308, written in the changelogs).

### 1.1 Facets, kinds and the slot table in the kernel

`claudia_core` only (facets note, phase 1, items 1–3).

* `claudia_core/facets.py`: `Facet`, the four facets, `facet_of`; `KINDS`; and the **slot table** above as data:
  `SLOTS_OF = {"paragraph": (...), "text": (box, words), "shape": (outline, label), "image": (box,),
  "diagram": (box,), "cell": (box, words)}` with each slot's facets and kind. One function, `slots_of(thing_kind)`,
  is what the server and (through the server) every client asks.
* `css.py` builds `_CHECKS` from the facets, `format_css` keeps its order; `ALLOWED_CSS` unchanged.
* `StyleDef.kind`; checks in `StyleBook.add` and `ChangeStyle`; deviation inherits kind; `views` and
  `StylesChanged` carry it.

**The table is open (D315).** Adding a row must not touch the style model, the server's style API or the UI
components: a test registers a made-up thing kind with a slot (say a "slide" with a `box` slot) in a test-only table
and styles it end to end through the API. That test is what keeps the later rows cheap.

**Done when** core's tests (new `test_facets.py`, extended `test_css.py`, `test_style_book.py`) are green; the apps
still run because 1.2–1.4 land in the same PR or right after — give every existing built-in a kind in this PR so
nothing breaks in between.

### 1.2 Objects: slots instead of one style per object (core + all three apps)

The floating objects are core's (`ObjectModel`, one object layer for all three apps), so this is done once.

* `ObjectBody.style` means **only** the container slot (box or outline); `ObjectBody.paragraph.style` **only** the
  words/label slot. `SetObjectStyle` and `SetParagraphStyle` check the style's kind against the slot.
* Built-ins in all three apps (`claudia_composes/model.py`, `claudia_creates/styles.py`,
  `claudia_computes/styles.py`): `plain-shape` → kind `outline` (fill, stroke, stroke-width only); new
  `shape-label` and `plain-box`; `plain-image` → `box`. A new shape's paragraph starts under `shape-label`, a new
  text box under `plain-box` + `body-text` (`STYLE_OF_KIND` and a new `PARAGRAPH_STYLE_OF_KIND` in
  `claudia_server/creates.py`, and wherever computes and composes create objects; `grep paragraph_for`).
* **Rendering keeps the look** — this is the one web change in step 1, because otherwise text boxes and shapes
  would draw wrongly: `slide-style.ts` (`textCss`/`pathCss` and their `PAINT` list) and the object drawing in
  composes and computes read the box slot from `ObjectBody.style` and the words from the paragraph's style.
  A text box's box is drawn as CSS on its element (D310), a shape's outline as SVG attributes.
* pptx import/export (`claudia_creates_io/pptx.py`): text box → `plain-box` + `body-text`, autoshape →
  `plain-shape` + `shape-label`.

**Done when** a deck, a workbook and a text with every object kind look pixel-for-pixel as before (screenshots
before/after in the PR) and the test-document runs (`scripts/run_test_documents.py`) are green.

### 1.3 Composes: the paragraph as a slot

* Composes' paragraph styles get kind `paragraph` (they may hold Box properties, e.g. Definition — composes'
  paragraph slot reads Box, Paragraph and Text).
* `TextModel.style_in_use` / `style_uses` count per slot, including the objects in the text.
* The Format menu's filter by id (`OBJECT_STYLE_IDS` in `TextWorkspace.vue`) is replaced by "kind fits the
  paragraph slot" — a list the server answers (1.5), so the menu shows the same entries as before.
* docx (`claudia_composes_io/docx.py`): unchanged mapping of the built-ins; check it still reads the kind-less
  defaults right.

**Done when** composes' tests and the docx test documents are green and the Format menu lists exactly what it
listed before.

### 1.4 Creates and computes objects: nothing app-specific left

After 1.2 the only per-app style code should be the built-in lists and the drawing. This step removes what is left:
creates' `set_paragraph_style` exists only in `claudia_server/creates.py` (the objects of a sheet or a text have no
way to restyle their words today), and creates' slide drawing has its own split of text and paint. Both go into the shared path
of 1.5 and the facet-driven drawing of 1.2.

**Done when** `grep -rn "plain-shape\|PAINT\|OBJECT_STYLE_IDS" web/app packages/*/src` finds only the built-in
definitions.

### 1.5 One style API on the server for all three apps

`claudia_server/styles.py` (`add_style_methods`, shared by the three apps today for the style book, the palette
and objects) becomes the only place a style is applied, for every thing in the slot table:

* `style_model` → `{facets, kinds, slots}` — the table of 1.1, so no client keeps a copy.
* `styles` → each style with `kind` (as today plus one field).
* `apply_style(target, slot, style)` and `deviate_style(parent, targets, slot, set|text)` where a **target** says
  what is styled in the app's own terms: `{"block": id}` (composes), `{"object": id}` (all three),
  `{"sheet": id, "range": [r0, c0, r1, c1]}` (computes, from 1.6). Each app registers how a target becomes a command
  (a small adapter per app, the way `ObjectModel` leaves anchors to the app). `slot` defaults to "all slots of the
  target" — that is D309/D311's "one bundle fills both".
* `style_uses` → how many things use each style, per slot.
* The existing methods (`set_style`, `deviate_style` of composes, `set_object_style`, `deviate_object_style`,
  `set_paragraph_style`) stay as **thin wrappers** over the new ones until step 2 has moved every client call, and
  are removed in 3.4. The protocol version stays 1 (methods are added); the changelog of `claudia-server` says so.

**Done when** server tests drive every row of the slot table through `apply_style` and `deviate_style` in the app
it belongs to (and get `command_error` for a style of the wrong kind), and the old methods' tests still pass
through the wrappers.

### 1.6 Cells get slots (computes backend)

Can start once 1.1 is merged, in parallel with 1.2–1.5; it needs 1.5 only for its last item. Detailed in facets
note phase 5 and D307.

* Allow-list v3: `vertical-align`, `white-space` in the Box facet; `CSS_VERSION = 3`.
* The built-in cell styles of D313 in `claudia_computes/styles.py`.
* `claudia_computes/cellstyles.py`: style ranges per sheet in **layers by shape** (sheet default, column, row,
  range — a single cell is a range), non-overlapping inside a layer (applying subtracts), `style_at`, `ranges_in`
  (window), `uses`, `MAX_STYLE_RANGES`. In `Sheet.to_data` / restore.
* `WorkbookModel.restructure` maps ranges with `StructuralEdit.map_span` as it maps `row_heights`/`col_widths`
  today, and returns what was cut so `Structure`'s undo puts it back exactly (D135's lesson).
* `SetCellStyle(sheet, range, box, words)` with `regions()` (cell locks) and an exact inverse; `style_in_use` counts
  cells, so a style that cells use cannot be taken back.
* Server: the cell target of 1.5, plus `cell_styles(sheet, window)` (same window rules as `cells`) and
  `cell_style_at` ("where does this cell's look come from").

Tests first: a seeded random sequence of styling, row/column inserts and deletes and undos checked against a
brute-force per-cell model (the repo has no Hypothesis; ask before adding it); layer order; locks; two authors
(pattern: `packages/claudia-core/tests/test_style_book.py`); a performance guard
`packages/claudia-computes/tests/test_cellstyle_performance.py` added to `check_debt.py`'s list next to
`test_index_performance.py` (a million styled cells in a few thousand ranges: lookup, window, row insert, snapshot).

**Done when** all of that is green and a cell can be styled, deviated, undone and moved through the server API —
with no UI yet.

---

## Step 2 — the new UI, in all three apps

**Done when (whole step):** in a browser and in the GTK and Windows/macOS shells, every thing in the slot table can
be styled through the same menus and dialogs, matching the mock-ups; the parity list in 2.6 holds for cells.

### 2.1 Mock-ups agreed (drawn during step 1)

Already agreed: `format-menu-apply-style.svg`, `all-styles-edit.svg`, `styles-model-facets-slots.svg`. New, in the
same style in `notes/mockups/`:

* `style-editor-two-slots.svg` — the popover and the All styles editor for a thing with two slots (a text box: its
  box and its words; a shape: outline and label): how a person sees which slot she is changing, "only the box",
  and one section per facet.
* `computes-cell-styles.svg` — a sheet with Header / Input / Result / Note cells and a styled empty column; the
  quick style list in the formula-bar row; Format ▸ Apply style with cells selected.
* `computes-cell-style-popover.svg` — Edit this style… on a cell: Text, Paragraph, Box (per-side borders, vertical
  alignment), "these cells only / every use", and where the look comes from ("column C's style").

**Done when** the owner approves them. Nothing in 2.2–2.6 is built before its drawing is agreed.

### 2.2 The shared components, built against slots

`web/app/lib` and `web/app/components`, tested with fake hosts in vitest — no app wired yet (facets note,
phases 2–3).

* `StyleHost` (`lib/style-host.ts`): `parts: {words, box}` → `target`, `slots` (from `style_model`), `slot` (the
  one being edited), `facets`; `apply`/`deviate` call the 1.5 API. One generic `styleHost(session, target)` instead
  of the per-app adapters where possible.
* `stylesForSlot(model, slot)` — the one function that decides what a menu offers.
* `StyleMenu.vue` with `mode: 'apply' | 'edit'`; `StyleSpec.vue` with one section per facet of the slot, left out
  (not disabled) otherwise, and the slot switcher of `style-editor-two-slots.svg`.
* `StylesDialog.vue`: Edit beside Rename ("Name it" for `to_name`), two panes.
* The Format menu block (Apply style ▸ with styled entries via an extended `previewCss`, Edit this style…, All
  styles…, separator, Colours…) as one shared builder that the three workspaces call — today each builds its own
  (`styleItems()` in `Workspace.vue`, `styleItem`/`customStyleItems` in `TextWorkspace.vue`, `SlideWorkspace.vue`).

**Done when** the components' tests are green and a page that mounts them with a fake host matches the mock-ups.

### 2.3 Composes

The paragraph host and the objects in the text on the new components; `StyleBar`'s quick list generalised to a
host (it is reused by computes in 2.6); Format menu from the shared builder; the client calls the 1.5 API.

### 2.4 Creates

Objects on the slide: the object host with two slots (text box, shape), images and diagrams with their one slot;
the context menu's "Style…" (`lib/object-menu.ts`) opens the new popover; Format menu from the shared builder.

### 2.5 Computes objects, and the shells

The floating objects of a sheet as in 2.4. Shells: `format.apply-style` in the three Format menus of
`clients/linux/src/claudia_shell_gtk/manifest.py`; `npm run generate-menu` / `check-menu` in `clients/windows`;
no change to `clients/contract/` (D301).

**Done when (2.3–2.5)** every row of the slot table except cells can be styled in each app, in the browser and both
shells, checked against the mock-ups with a screenshot per row in the PR.

### 2.6 Cells in the grid

* The cell host (target `{sheet, range}` from the selection); which host the menus use follows the selection
  (object selected → its host; cells → the cell host).
* `SheetGrid.vue` paints style ranges for the **visible window only**: one element per visible range for
  backgrounds, styled cell elements (including empty cells with a border or background) inside the window; the
  number of elements is bounded by the screen, never by the sheet. Ranges are fetched with the cells and again on
  `StylesChanged` and structure events.
* The quick list in the formula-bar row, Format ▸ Apply style, Edit this style… and Shift+F10 at the active cell,
  "where the look comes from".

**Done when** a cell does everything a composes paragraph does:

| A paragraph in composes | A cell in computes |
|---|---|
| one named style, no direct formatting | the same (both slots, D311) |
| Format ▸ Apply style ▸ | the same, for the selected cells |
| quick list in the toolbar | the same, in the formula-bar row |
| Edit this style… / Shift+F10 at the caret | the same, at the active cell |
| "this paragraph only" → a `to_name` style | "these cells only"; "only the box" deviates one slot |
| All styles… with Edit | the same dialog |
| a change reaches every paragraph that has it | every cell, row, column and sheet default |
| use counts in the gallery | counted from ranges |
| palette roles; Colours… | the same |
| undo per author; locks; the AI is another user | the same |

…and a styled column of a million rows scrolls as smoothly as an unstyled one (measured).

---

## Step 3 — finish

* **3.1 File formats.** docx and pptx checked once more against the test documents. **xlsx is not touched** for
  cell styles (D314): an exported workbook carries values and formulas as today; cell styles in xlsx and ODS are
  E6.18, a later round. Add a test that the `xl/styles.xml` part of an exported workbook is the same with and
  without cell styles applied, so nobody starts writing it by accident.
* **3.2 The AI user.** `claudia-ai` calls none of the style methods today; give it `apply_style`, `deviate_style`
  and `styles` if the owner wants the AI to style (it is just another user, so the same locks and undo apply).
* **3.3 Accessibility and i18n.** Flyout and popover keyboard-operable and announced (E5.10); styled menu entries
  readable in dark mode (the palette's readings, D202, decide); every new label through `t()`.
* **3.4 Clean-up.** Remove the wrapper methods of 1.5 and the per-app adapters left over; `check_debt.py` clean;
  coverage floors held.
* **3.5 Docs and log.** Sphinx pages, help pages (`claudia_composes/help/editing-a-style.md` and computes' own),
  changelogs (`docs/changelog*.md`), backlog (E1.10, E1.11, E5.13, E5.14, E6.13, E9.7), an implementation note of
  what was built, D-numbers for anything decided on the way (D316–D319 are free in the block).

## Order, and what can run at once

```
step 0 ─ 1.1 ─┬─ 1.2 ─ 1.3 ─ 1.4 ─ 1.5 ─┐
              └─ 1.6 (cells backend) ───┤        (2.1 drawn during step 1)
                                        ├─ 2.2 ─ 2.3 ─ 2.4 ─ 2.5 ─ 2.6 ─ step 3
```

Two agents can work at once from 1.1 on: one on 1.2–1.5 (objects, composes, the API), one on 1.6 (cells). In step 2,
2.3–2.5 can be split by app once 2.2 is merged; 2.6 needs 1.6 and 2.2.

## Risks

* **Step 1 is invisible but wide.** It touches every app's built-ins, the object drawing and the server. The
  pixel comparison of 1.2 and the test-document runs are what make "nothing changed on screen" checkable.
* **Style ranges** (overlap, layers, structure edits, undo) — non-overlapping layers and the brute-force test
  written first.
* **One API for three apps** — the target adapters must stay small; if one app needs more than a target → command
  mapping, that is a sign the slot table is wrong, and a reason to stop and ask.
* **Grid speed** — measured as part of 2.6's done.

## The gate (every pull request)

```
uv run pytest
uv run pytest --cov && uv run python scripts/check_coverage.py
uv run python scripts/check_debt.py                  # lint, types, dead code, docs, performance guards
uv run python scripts/api_surface.py --write         # read the diff of tests/api/*.json; bump and changelog
uv run sphinx-build -W -b html docs docs/_build/html
cd web && npx vitest run && npx nuxt typecheck
cd clients/windows && npm run check-menu             # from 2.5
```

`tests/test_decision_log.py` (part of `pytest`) keeps every cited `D<n>` real.
