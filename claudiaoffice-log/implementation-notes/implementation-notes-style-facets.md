# Styles as facets, slots and bundles (E1.11, E5.14, E6.13; D300–D310)

For the agent that writes the code. The decisions are D300–D310 in `claudiaoffice-log/decision-log/`; read them
first, they are short. This note says **what to change on `main`**, in what order, with which tests. It was written
against `main` at `08ffcb9` (2026-11-10). Where it names a file or a function, that name was read on that commit;
where it proposes a new one, it says so. If something here no longer matches the code, trust the code and the
decisions, and tell the owner what moved.

Mock-ups the UI half is built from (agreed with the owner, do not redesign):
`notes/mockups/format-menu-apply-style.svg`, `notes/mockups/all-styles-edit.svg`,
`notes/mockups/styles-model-facets-slots.svg` (the model). UI work starts from those, not from code (project rule).

Working rules that apply to every phase: tests first (TDD); one commit per phase on the feature branch the owner
names; the gate of the last section passes before a phase is handed over; every new public name goes into the API
snapshot and the changelog (`docs/versioning.md`); decisions are cited as `D303`, never invented — if you need a
decision, ask for one in the block **D300–D319** (D311–D319 are free).

## The model in one screen

```
Style  = id, name, purpose, based_on, kind, css (property bag in CSS notation), to_name
Facet  = a named set of properties, with their value checks and their render/export mappings
           Text       font-family font-size font-weight font-style text-decoration color letter-spacing word-spacing
           Paragraph  text-align line-height margin-top/right/bottom/left
           Box        background-color border-top/right/bottom/left padding-top/right/bottom/left vertical-align*
           Outline    fill stroke stroke-width
Slot   = a place that reads a style: it names the facets it reads and the kind a style must have to be offered
           composes paragraph   Box + Paragraph + Text   kind paragraph
           object words         Paragraph + Text         kind paragraph (text box, shape label, and a cell's words)
           object box           Box                      kind box      (text box, cell box, chart)
           object outline       Outline                  kind outline  (shape)
           picture              nothing                  kind box      (a picture carries its own colours)
Kind   = paragraph | box | outline (D312) : which facets a style may hold, and so which slots may use it
```

`*` `vertical-align` and `white-space` are new (D307, allow-list `CSS_VERSION` 3, phase 5 only).

Two rules that decide most questions you will have:

* **A slot reads only its facets and ignores the rest** (D304, D309). A `Definition` in composes holds Box and Text
  properties and is used by a composes paragraph, which reads all three. The same style used as a text box's words
  would have its Box part ignored — and the editor must not show a section the slot cannot read.
* **No direct formatting** (D306). Nothing in this work adds per-run or per-word styling. `Paragraph.runs` stays
  authorship (who wrote which characters), never styling.

## What is on `main` today (so you know what you are changing)

* `claudia_core/css.py`: one flat `_CHECKS` table (property → value check), `ALLOWED_CSS = frozenset(_CHECKS)`,
  `_ORDER` from the table's order, `CSS_VERSION = 2`, `validate_css`, `parse_css`, `format_css`, `resolve_css`.
* `claudia_core/styles.py`: `StyleDef(id, name, purpose, based_on, css, to_name)` with `to_data`/`from_data`;
  `StyleBook` (`computed`, `chain`, `children`, `views`); commands `CreateStyle`, `ChangeStyle`, `RenameStyle`,
  `RemoveStyle`, event `StylesChanged`.
* `claudia_core/objects.py`: `ObjectBody(id, kind, w, h, style, paragraph, shape, image, imported, diagram, rotation,
  snap)`; `paragraph_for(object_id, style, text, author)` gives a new object's paragraph **the object's own style**;
  `SetObjectStyle` (line ~1357), `SetParagraphStyle` (~1407). `claudia_core/paragraphs.py`: `Paragraph(id, style,
  text, runs)`, immutable.
* The built-ins: `claudia_composes/model.py` (`BUILTIN_STYLES`, includes `plain-shape`, `plain-image`, and
  `definition` with `background-color`, `border-left`, `padding-*`), `claudia_creates/styles.py`,
  `claudia_computes/styles.py`. In creates and computes `plain-shape` mixes **Outline** (`fill`, `stroke`,
  `stroke-width`) with **words** (`font-size`, `line-height`, `text-align`) in one style — that mix is what is
  being split. In `claudia_server/creates.py`: `STYLE_OF_KIND = {"text": "body-text", "shape": "plain-shape",
  "image": "plain-image"}` — note that a **text box's object style is `body-text`**, a words style used as a box
  style; that is the other thing being cleaned up.
* `claudia_server/styles.py`: `add_style_methods` registers `styles`, `change_style`, `rename_style`, `check_css`,
  palette methods, `set_object_style`, `deviate_object_style` (and composes has `deviate_style`, `set_paragraph_style`).
  `own_css`, `_only_what_differs` are helpers there.
* Web: `lib/style-host.ts` (`StyleHost`, `Parts {words, box}`, `StyleEditor`), `lib/object-style-host.ts`
  (`objectStyleHost`, `partsOf(kind)`, `nounOf`), `lib/text-style-host.ts`, `lib/slide-style.ts` (`textCss`, `pathCss`
  split by a hard-coded `PAINT` list), `lib/style-css.ts` (`previewCss`, `StyleView`),
  `components/{StyleMenu,StyleSpec,StylesDialog,StyleBar}.vue`, and the three Format menus in
  `TextWorkspace.vue` (composes: `styleItem`, `customStyleItems`, `OBJECT_STYLE_IDS` — filtering **by id**),
  `Workspace.vue` (`styleItems()`, computes) and `SlideWorkspace.vue` (creates).
* Shells: `clients/linux/src/claudia_shell_gtk/manifest.py` (three Format menus: `format.look` "Edit This Style…",
  `format.all-styles`, `format.colours`, all `_page(...)` actions), `clients/windows/src/generated/menu.<app>.json`
  generated from it (`npm run generate-menu`, `npm run check-menu` fails on drift).

## Phase 1 — facets and kinds in the kernel (E1.11, D303, D305)

Goal: no behaviour change a user can see, except that a style has a `kind` and a bad property for its kind is refused.

1. **Facet table.** New module `claudia_core/facets.py`:
   `Facet(name, properties)` frozen dataclass; the four instances `TEXT`, `PARAGRAPH`, `BOX`, `OUTLINE`; `FACETS`;
   `facet_of(prop) -> Facet`; `KINDS: dict[str, tuple[Facet, ...]]` (`paragraph` → Text, Paragraph, Box; `box` → Box;
   `outline` → Outline); `SLOTS` (see the table above) with `reads` and `kind`.
   Value checks stay where they are, in `css.py` (they are CSS value syntax); `facets.py` holds names only and
   `css.py` builds `_CHECKS` from the facets. Add an import-time assertion and a test that the set of facet
   properties equals `ALLOWED_CSS` — a property in no facet, or in two, fails the test. *This is the one place the
   decision says "a facet owns its vocabulary, checks and mappings": today the facet owns the vocabulary and
   `css.py` the CSS checks; a facet that is not CSS-checkable (Outline for a non-web target) gets its own checks
   when a second target needs them. Do not build that speculatively.*
2. **Order of `format_css`.** It currently follows `_CHECKS` order. If deriving `_CHECKS` from facets changes the
   order, keep the old order with an explicit `_ORDER` list, so the CSS text a person sees does not reshuffle.
3. **`StyleDef.kind: str`.** Add the field (after `based_on`), to `to_data` and `from_data` (no upcast: D308), to
   `CreateStyle`'s data, to `StyleBook.views` (`kind` in each view), and to the `StylesChanged` event. `StyleBook.add`
   and `ChangeStyle` refuse a property whose facet the style's kind does not allow, with a sentence that names the
   property and the kind (“`fill` is not a property of a paragraph style”). A style made by deviating gets its parent's
   kind (`deviate_style`, `deviate_object_style`).
4. **Built-ins carry a kind** in all three apps. The split (D310):
   * `plain-shape` → kind `outline`: `fill`, `stroke`, `stroke-width` only.
   * new `shape-label` → kind `paragraph`, based on `body-text`: `text-align: center`, and where the app had them
     `font-size`/`line-height` (creates: `36px`, `1.25`).
   * new `plain-box` → kind `box`, no properties: what a text box has by default; it exists so that the object box
     slot of a text box does not have to point at a paragraph style.
   * `plain-image` → kind `box`, no properties (unchanged otherwise).
   * `body-text` and the rest of composes' styles → kind `paragraph`; composes' `definition` is `paragraph` (it holds Box
     properties, which composes' paragraph slot reads).
5. **Slots in objects.** `paragraph_for` keeps its signature; its caller decides the style. Add
   `PARAGRAPH_STYLE_OF_KIND = {"text": "body-text", "shape": "shape-label"}` next to `STYLE_OF_KIND` in
   `claudia_server/creates.py` (and where computes/composes create objects — `grep paragraph_for`; also
   `claudia_creates_io/pptx.py`, which defaults to `body-text`/`plain-shape` and must now give a shape a
   `shape-label` paragraph) and change `STYLE_OF_KIND["text"]` to `plain-box`. An object's `style` is then **only**
   its box/outline; its `paragraph.style` is **only** its words. `SetObjectStyle` and `SetParagraphStyle` check the
   kind of the style they are given against the slot (a `paragraph` style cannot become an object's box).
6. **Server.** `styles` answers `kind` per style. New read method `style_model` (additive, no `write`): `{version,
   facets: {name: [props]}, kinds: {kind: [facet names]}, slots: {slot: {reads: [...], kind}}}` — the web must not
   keep its own copy of these tables (the lesson of `palette`: the copy is the one that drifts). Document it in the
   method's docstring like its neighbours; the API reference is generated from them.
7. **Composes' filter by id goes.** Delete `OBJECT_STYLE_IDS` in `TextWorkspace.vue`; `customStyleItems` and
   `styleItem` take styles whose `kind` fits the `composes paragraph` slot.

Tests first, in `packages/claudia-core/tests/` (`test_facets.py` new, `test_css.py`, `test_style_book.py`,
`test_objects.py`): every allowed property is in exactly one facet; each kind allows what the table says and refuses
the rest with the property named; deviation inherits kind; `to_data`/`from_data` round-trip with `kind`; creating a
style of a wrong kind is refused as `command_error` through the server; `SetObjectStyle` with a `paragraph` style is
refused; two-author conflict case for `ChangeStyle` stays green; every built-in of each app passes its own kind
(this test catches the split). Server: `style_model` answer matches the core tables.

`CSS_VERSION` stays 2 in this phase (no property is added). `tests/test_css.py` asserts `== 2`; leave it.

## Phase 2 — the Format menu and the popover (E5.14, D300, D301, D305)

Mock-up: `format-menu-apply-style.svg`.

* **Web, all three Format menus** (`TextWorkspace.vue`, `Workspace.vue`, `SlideWorkspace.vue`): four entries,
  `Apply style ▸` (submenu), `Edit this style…`, `All styles…`, then a separator, then `Colours…`. `MenuBar.vue`'s
  `MenuItem` already has one level of flyout (`items`, used by “Paste as”, computes' Row ▸ and Column ▸, D130); it
  needs only a way to draw an item in a style's look. Keep ids: `format.look`, `format.all-styles`,
  `format.colours`; add `format.apply-style`.
* **The look of an entry**: `previewCss(s.resolved)` already exists (`StyleMenu.vue` uses it) and drops size; extend
  it, do not add a second function, to give: font-family, weight, italics, decoration, colour, and for a style with a
  Box `background-color` a small chip. Never the font size. Do **not** use the facet table to guess; use the style's
  `resolved` CSS.
* **Which styles are offered**: those whose kind fits the slot the selection is in (`composes paragraph`; for a
  selected object its `object words` when editing its text, its `object box` or `object outline` otherwise). One
  function, `stylesForSlot(model, slot)`, in `lib/` and tested; the three menus use it.
* **Native shells (D301)**: GTK `manifest.py` — in each of the three Format menus replace the first block with
  `_page("format.apply-style", "Apply Style…", "Choose a style for the selection, drawn in its own look")` placed
  before `format.look`; the existing groups stay as they are. No new message in `clients/contract/` — the shell sends
  the action id to the page and the page opens its popover, exactly like `format.all-styles`. Regenerate the Windows
  menu JSON (`npm run generate-menu` in `clients/windows`), `npm run check-menu` must pass. macOS uses the same
  generated JSON. No `webroutes.json` or `shim.js` exists on `main` at `08ffcb9`, and `format.all-styles` is wired only in the three
  workspace components and `manifest.py`; do the same for `format.apply-style`, and check
  `lib/menu-dispatch.ts` (the web side's walk of menu ids) for where an id is registered.
* **Popover** (`StyleMenu.vue`, `Popover.vue`): the gallery is already there (`v-for="s in host.styles"`); make it
  the list `stylesForSlot` returns, and let the `format.apply-style` action open it at the caret / selection. Note
  `StyleMenu`'s own docstring says that clicking a gallery row only *picks which style the panel below shows*
  (UX-14) and never applies. The popover for **Apply style** is a different mode: clicking a row *applies* it and
  closes. Make that an explicit prop (`mode: 'apply' | 'edit'`) on the one component rather than a second component.
* i18n: new labels go through `t()`; run `scripts/extract_i18n.py` per the i18n notes.

Tests: `web/tests/` for `stylesForSlot`, the extended `previewCss`, the menu structure (four entries in this
order, a separator before Colours), and `check-menu` for the shells. `clients/linux/tests/test_manifest.py` gets
the expectation for `format.apply-style` in all three apps.

## Phase 3 — Edit in All styles, two-pane editor (E5.14, D302, D303, D309)

Mock-up: `all-styles-edit.svg`.

* `StylesDialog.vue`: every row gets **Edit** beside **Rename** (a style waiting for a name shows **Name it**).
  Edit puts the dialog into two panes: the list stays left; right, the editor of the chosen style. The editor is
  `StyleSpec.vue` (it already is the controls/CSS switch) plus **one section per facet the style's kind holds**.
  `StyleSpec` today shows groups by `host.parts`; change it to take the list of facets from the *slot* being edited
  (from `style_model`), and keep "left out, not disabled" (D209).
* `StyleHost` (`lib/style-host.ts`): replace `parts: {words, box}` by `facets: string[]` (the facets of the
  slot the host styles). `partsOf(kind)` in `object-style-host.ts` becomes a lookup in the server's slot table —
  keep a small pure function so the tests do not need a server. `textStyleHost` is `facets: [Box, Paragraph, Text]`
  (it was `words: true, box: false` — composes' Definition makes Box real there).
* **“Change the box only” / “this paragraph only”** is `host.deviate(edit)` as before, but the edit now touches one
  slot (D309): `deviate_object_style` makes the new style from the *box* style, and a new `deviate_object_words`
  (mirror of composes' `deviate_style`, from the paragraph's style) makes it from the *words* style. Both give
  the provisional name and `to_name` (D75). The dialog says which slot is being changed in its header (“Plain box
  of this text box” / “Body text of this text box”).
* Rename keeps its rules (`rename_style`); deleting styles is still **undecided** (D226). Do not build it.

Tests: `style-editor.test.ts` additions: the editor for a `paragraph` style in an `object words` slot shows Text and
Paragraph sections and no Box section; Edit opens, Rename still works; the deviation target is the slot, not the
object. Server: `deviate_object_words` creates one style, points one paragraph, nothing else (undo restores).

## Phase 4 — outline and box in the renderers (D310)

* `slide-style.ts`: `textCss`/`pathCss` filter by a hard-coded `PAINT` list. Replace by facet membership from the
  `style_model` answer: the **words** slot gets Paragraph and Text properties (and its own paragraph's
  `resolved`), the **box** slot gets Box properties (`background-color`, `border-*`, `padding-*`) as CSS on the
  text box's element, the **outline** slot gets Outline properties as SVG attributes on the path. A text box is now
  drawn as an element with its box CSS and its paragraph inside — `SlideCanvas.vue` and the computes object layer
  (`Workspace.vue`/`SheetGrid.vue`) and composes' object overlay each have a draw path for text objects; find them
  with `grep -n textCss web/app`. A shape keeps `fill`/`stroke`.
* Export: `claudia_creates_io/pptx.py` (shape fill/line → `plain-shape`; text box → `plain-box` + `body-text`),
  `claudia_computes_io` (xlsx drawings) and `claudia_composes_io` have mappings for the object style: read them
  with `grep -rn "plain-shape\|plain-image\|body-text" packages/*-io`. Behaviour to keep: the round-trip tests in
  `test-documents/` (`scripts/run_test_documents.py`) stay green; an imported autoshape gets `plain-shape` +
  `shape-label`.

## Phase 5 — cell styles (E6.13, D307)

Only after phases 1–4. Needs its own mock-up first if the style dialog or the grid changes visibly (it should
not: a cell opens the same menu through a `cellStyleHost`).

* Core allow-list: add `vertical-align` (`top|middle|bottom`) and `white-space` (`normal|nowrap|pre-wrap`) to the
  Box facet and bump `CSS_VERSION` to 3 (`test_css.py` asserts the number; update with a comment like the existing
  one). Both only in `box` kind.
* `claudia_computes`: a per-sheet table of **style ranges in layers by shape** (sheet default, column, row, range;
  a single cell is a range), looked up in that fixed order with the most specific winning (D307), and
  non-overlapping inside a layer (applying a range subtracts it from what is there); stored as ranges, not per cell;
  a command `SetCellStyle(sheet, range, box_style, words_style)` — applying a style fills both (D311)
  that respects locks and has an inverse built from the state it found (see `SetObjectStyle` for the shape of
  such a command), logged and undoable per author; ranges **move with row and column insertions and deletions**
  (D135 — look at how line sizes move today and do the same). Property tests for the range table: any sequence of
  structure edits keeps `style_at(cell)` equal to a brute-force per-cell model.
* Server: `set_cell_style` (range, which slot, style id), `cell_style_at` (for the dialog's “where does this cell's
  look come from”). Document both.
* Web: `cellStyleHost`; `SheetGrid.vue` draws styled empty cells without an element per cell (paint from the
  range table per visible row/column band — measure with a million styled cells; E6.13 asks for it).
* **Not in this phase**: number formats (separate, D75, E6.14), row height and column width (layout, D135, E6.16),
  conditional formats.

## Deliberately not done in this round

* **Inline marks** (D306). The model leaves room (`kind` could grow `mark`, a slot `composes paragraph marks`) and
  nothing else is prepared. Do not add a `runs`-style styling array, and do not add “this word only”.
* **Deleting styles** (D226). **Hiding** built-ins likewise.
* **A second render target for Outline or Box** beyond what the exporters above need today.
* **Migration** of old documents (D308): old snapshots without `kind` fail to load, on purpose. Record it in the
  changelog of each touched package (`docs/changelog.md` for the kernel, `docs/changelog-<package>.md` for the
  others).

## Gate (every phase)

```
uv run pytest                                           # all packages
uv run pytest --cov && uv run python scripts/check_coverage.py
uv run python scripts/check_debt.py                     # lint, types, dead code, docs, performance guards
uv run python scripts/api_surface.py --write            # then read the diff in tests/api/*.json
uv run sphinx-build -W -b html docs docs/_build/html
cd web && npx vitest run && npx nuxt typecheck           # web
cd clients/windows && npm run check-menu                 # shells, from phase 2
```

`tests/test_decision_log.py` must stay green: every `D<n>` you cite in code, docs or a changelog must exist.
A decision that this work makes obsolete is replaced, not edited (`git mv`, `status: superseded`,
`superseded-by`; see the log's README).

## Questions that are the owner's, not yours

* Settled since this note was written: GTK opens the popover too (D301); the kinds are `paragraph | box | outline`
  (D312); cells fill both slots (D311); the built-in cell styles (D313); no xlsx for cell styles in this round
  (D314); the slot table is open for later slots (D315). The order of work is in
  `implementation-notes-styling-suite-plan.md`, which takes precedence over the phase order here.
* If phase 1 shows a better closed list of kinds, change it in the code *and* write a decision — do not drift.
* The exact label of the first entry (“Apply style” in the web menu, “Apply Style…” in a native menu, which uses
  title case and an ellipsis for entries that open something).
