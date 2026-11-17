# The floating object layer in composes

Written 2026-11-17. Follows `rotation-ui-and-the-composes-object-layer.md` (2026-11-15), which asked for the layer and
drew it before it existed. This note records what was found when the layer was looked at again, what was fixed, the
design of the rest, and what has to be decided. No decision-log entries are written here; the ids come from the
range the owner hands out.

Mock-ups, in `notes/mockups/`:

| File | Shows |
|---|---|
| `composes-object-layer.svg` / `.png` | Every kind of object at its character, held and let go, Edit ▸ Image… and the one import dialog, the placement rule, the numbers |
| `composes-object-wrap.svg` / `.png` | **Proposal, not built.** Four ways text can flow around an object, the Wrap Text… popover, the rules, the Word and LibreOffice mapping, open points |
| `composes-object-layer-architecture.svg` / `.png` | Where the code lives layer by layer (built / this patch / proposed) and the three ways of laying out lines round an object |

## What was wrong (found 2026-11-17, all fixed in the patch that came with this note)

| | Bug | Size | Fix |
|---|---|---|---|
| A | A selected object kept its outline after a click into the text: nothing cleared `selectedObject` when the person turned back to the words. | 3 | `TextEditor.vue` lets go of the selection on any press or focus outside `[data-object]` (`letsGoOfObject`, pure and tested). |
| B | The screen hung an object at the right edge of its paragraph; print hangs it at its anchor character. The model has kept `dx`/`dy` since D1023 and neither the screen nor `layoutText` read them. | 2 | One rule for both: the anchor character's spot plus `dx`/`dy`, kept inside the text column. `floatBox`, `layoutText`, `BlockAnchor` (web and layout types). |
| C | Imported pictures, shapes and text boxes were invisible in the editor: only `rendered` containers were drawn. | 2 | `TextContainers.vue` draws every kind through `lookOf`; `TextSession` now keeps `shapes`. A chart says it is not shown yet instead of leaving a gap. |
| D | The rotation note said the model had no offset. | 3 | Status lines added to that note. |
| E | composes had no way to put a picture in, and creates and computes each had a copy of the import dialog. | 3 | One `ImageImportDialog.vue` with an `add(picture, aspect)` function; Edit ▸ Image… (`edit.image`, Ctrl+Alt+I) in composes, in the manifest, the key table and the German catalog. |

## The rule for where an object hangs

`left = clamp(character.left + dx, column.left, column.right − w)`, `top = max(0, character.top + dy)`. Print adds the
bottom margin (an object is moved up to stay on its page). Both read the same two numbers from the same anchor.

The screen measures the character with a `Range` on the browser's own line; print measures it on the engine's line.
Those two can differ by a few pixels, so "what you see is what is printed" holds up to that difference. It is not
tested against a rendered page: there was no browser in the session that built this.

## Wrap: the proposal (nothing of it is built)

Four modes, kept in the anchor beside `dx`/`dy` (it is composes-only, and `MoveObject` already replaces the whole
anchor): **over the text** (today, the default, so no document changes), **around** the object, **above and below**,
**behind** the text, plus a distance in pixels. Rules, in short: the object's place is worked out from the layout
*without* its own wrap, so no loop is possible; objects are taken in the order of the text and only change lines at
and after their top; a line takes the free stretches of its own band, and a stretch narrower than 3 em is not used.
The full list is on the mock-up.

Where it would go: `layout/src/flow/exclusions.ts` (new, pure, integers), `layoutParagraph` taking a width per line
instead of one width, `paginate` handing it the bands that reach its page; the model field and a `set_wrap` method
(`MoveObject` with the old anchor and the new wrap, so the history says what happened); `format.wrap-text`
(Ctrl+Alt+L, free in the three manifests) with a popover like Rotate By….

### The decision that shapes it: who lays out the lines

The editor's lines are the browser's (contenteditable). Print and the print preview use the engine. Three ways:

1. **Wrap in print only.** Least work; the editor keeps showing objects over the words, so what you see is not what
   prints for exactly the objects that matter.
2. **The engine lays out the editor too.** Exact, and a rewrite of caret, selection, input methods, spell checking and
   the screen-reader tree (BITV).
3. **Engine exact, floats in the editor, in two stages.** Stage 1 is option 1. Stage 2 puts a non-editable float of
   the object's size at the anchor's line in the editor. *CSS floats wrap on one side only*, so an object in the middle
   of the column wraps on its wider side in the flow view while print shows both sides; a test compares which lines get
   narrowed.

*Recommended:* option 3, stage 1 first, stage 2 when it is asked for. It keeps contenteditable, and it keeps the rule
that the engine is the one place that decides how a document renders.

### Import and export

| Claudia | DOCX (`wp:anchor`) | ODF (`style:wrap`) |
|---|---|---|
| over the text | `wrapNone` | `run-through`, foreground |
| around | `wrapSquare` + `dist*` | `parallel` + `fo:margin` |
| above and below | `wrapTopAndBottom` | `none` |
| behind the text | `wrapNone`, `behindDoc` | `run-through`, background |

Tight, through and in-line are not modelled: they come in as the nearest of the four and the original is kept and
written back. The ODF values are from memory of what LibreOffice writes and have to be checked against a file it wrote
before any import code is written (as with rotation). The importers were not read for this note.

## Open points (each with a recommendation; the first two need the owner)

1. **Who lays out the lines** (above). Recommended: option 3, stage 1 first.
2. **A behind object cannot be clicked** without taking the caret from the text. Recommended: Tab and Edit ▸ Select
   Next Object reach it, and so does a click on its visible edge.
3. **One key or four.** Every menu entry has a key. Recommended: one entry, Wrap Text…, with the four modes as a radio
   group inside; four entries would need digit keys, which German AltGr uses.
4. **Default wrap for a new picture.** Recommended: above and below for pictures from Edit ▸ Image…, over the text for
   containers. The owner's call.
5. **Moving by dragging.** The offset exists and nothing sets it by hand. Recommended: drag the held object; the ring
   stays and the offset follows the pointer, snapped to the object's own grid (D214), one step per drag.
6. **Menu home of Image….** The earlier mock put it under Insert; Edit ▸ Image… is built because creates and computes
   have it there and one entry has one key in all three apps.
7. **Technical debt:** `SlideCanvas.vue` still draws pictures, shapes and boxes itself. `lookOf` is the same facets in
   plain data; moving creates onto it is a later, small change and was not done here, since it cannot be checked
   without a browser.

## Not verified

- No browser was available: `TextContainers.vue`, `TextEditor.vue` (the Range measurement, the capture handler) and the
  dialog wiring in the three workspaces were type-checked only in their `.ts` parts and never run. Firefox, the main
  testing browser, has not seen any of it. Please click through: insert a picture, hold and let go of an object, a
  LaTeX container in the middle of a line.
- `layout/tests/composes.test.ts` has a new test for the offset in print; it needs the pinned fonts, which the session
  could not fetch, so it was written but not run.
- The i18n catalogs got the one new string by hand, with its place line; `scripts/extract_i18n.py` followed by
  `update_po.py` and `po_to_json.py` will refresh every place line.
- The full quality gate (ruff, mypy, the Playwright run, the Python suites) was not run; vitest (the touched web
  tests) and `clients/linux/tests/test_manifest.py` were.
