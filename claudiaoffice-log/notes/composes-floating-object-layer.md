# The floating object layer in composes

Written 2026-11-17. Follows `rotation-ui-and-the-composes-object-layer.md` (2026-11-15), which asked for the layer and
drew it before it existed. This note records what was found when the layer was looked at again, what was fixed, the
design of the rest, and what has to be decided. No decision-log entries are written here; the ids come from the
range the owner hands out.

Mock-ups, in `notes/mockups/`:

| File | Shows |
|---|---|
| `composes-object-layer.svg` / `.png` | Every kind of object at its character, held and let go, Edit ▸ Image… and the one import dialog, the placement rule, the numbers |
| `composes-object-wrap.svg` / `.png` | **Decided 2026-11-17, not built.** Four ways text can flow around an object, the one cycling key, the Ctrl grab cursor, the rules, the Word and LibreOffice mapping, what is decided and what is open |
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

## Wrap: decided on 2026-11-17 (D1061–D1064), built on 2026-11-18 except the flowing editor (CODE-64)

Four modes, kept in the anchor beside `dx`/`dy` (it is composes-only, and `MoveObject` already replaces the whole
anchor): **over the text** (what a document with no wrap saved means, so no document changes; a new object starts as *above and below*, D1061), **around** the object, **above and below**,
**behind** the text, plus a distance in pixels. Rules, in short: the object's place is worked out from the layout
*without* its own wrap, so no loop is possible; objects are taken in the order of the text and only change lines at
and after their top; a line takes the free stretches of its own band, and a stretch narrower than 3 em is not used.
The full list is on the mock-up.

Where it would go: `layout/src/flow/exclusions.ts` (new, pure, integers), `layoutParagraph` taking a width per line
instead of one width, `paginate` handing it the bands that reach its page; the model field and a `set_wrap` method
(`MoveObject` with the old anchor and the new wrap, so the history says what happened); `format.wrap-text`
(Ctrl+Alt+R, free in the three manifests), one key that cycles the four modes.

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

*Decided (D1062):* option 3, stage 1 first, stage 2 when it is asked for. It keeps contenteditable, and it keeps the rule
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

## Decided, and what is still open

1. **Who lays out the lines.** Decided (D1062): the engine first, for print and the print preview.
2. **A behind object.** Decided (D1063): Ctrl held while the pointer is over the object's area turns the cursor into a
   hand, and a click takes the object. Without Ctrl a click in the words places the caret. Tab and Edit ▸ Select Next
   Object reach it without a pointer.
3. **One key.** Decided (D1064): Format ▸ Wrap Text, `format.wrap-text`, Ctrl+Alt+R; each press moves to the next of
   the four modes and back to *over*. Where the distance is set is **open** (the key does not carry it).
4. **Default wrap for a new object.** Decided (D1061): *above and below*, for what the person puts in. A document with
   no wrap saved stays *over*; imported objects keep the file's wrap. **Proposed, not confirmed:** switch the default on
   only when the editor draws the wrap (stage 2), because until then a new picture would print wrapped and show over
   the words.
5. **Moving by dragging.** The offset exists and nothing sets it by hand. Recommended: drag the held object; the ring
   stays and the offset follows the pointer, snapped to the object's own grid (D214), one step per drag.
6. **Menu home of Image….** The earlier mock put it under Insert; Edit ▸ Image… is built because creates and computes
   have it there and one entry has one key in all three apps.
7. **Technical debt:** `SlideCanvas.vue` still draws pictures, shapes and boxes itself. `lookOf` is the same facets in
   plain data; moving creates onto it is a later, small change and was not done here, since it cannot be checked
   without a browser.

## What was built (2026-11-18)

- **Engine** (`layout/src/flow/exclusions.ts`): a paragraph is laid out in *rows*; a row's width is the free stretches
  of its band, an exclusion is the object's box plus the gap, on both sides of an object (the text goes on at the right
  of a left-hand object and at the left of a right-hand one), a stretch under 3 em is not used. No widow/orphan rule
  is applied beside an object. An object's rotation is ignored for its exclusion (its unrotated box is used).
- **Model, server, files.** `BlockAnchor.wrap/gap`, `SetObjectWrap` (one undo step, "Wrap text"), `set_wrap`,
  `add_object` and `shapes` from the module shared with creates (D1065), ODF/DOCX mapping (D1066).
- **Web.** Edit ▸ Image…, Text Box and Shape; Format ▸ Wrap Text (Ctrl+Alt+R) cycles the modes; a second object layer
  under the words for *behind*, and Ctrl brings it up with a hand cursor (D1063); the accessible name says the wrap.

## Reuse across the three apps (checked 2026-11-18)

Shared: `ObjectBody`, the commands, `Placement`, `add_object_methods`, `add_shape_methods`, `lookOf` and the layer
component for pictures, shapes and boxes. Per app: the anchor and its placement. Not shared yet: `SlideCanvas.vue`
draws creates' objects itself; computes has no shapes or text boxes.

## Not verified

- No browser was available: `TextContainers.vue`, `TextEditor.vue` (the Range measurement, the capture handler) and the
  dialog wiring in the three workspaces were type-checked only in their `.ts` parts and never run. Firefox, the main
  testing browser, has not seen any of it. Please click through: insert a picture, hold and let go of an object, a
  LaTeX container in the middle of a line.
- `layout/tests/composes.test.ts`: the offset test was written without being run and was wrong (it looked for the clip
  of a *shape*, which has none); run with the fonts present, it now uses a text box and passes.
- The full quality gate (ruff, mypy, the Playwright run, the Python suites) was not run; vitest (the touched web
  tests) and `clients/linux/tests/test_manifest.py` were.
