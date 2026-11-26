# Object interaction: one contract for creates, computes and composes

Written 2026-11-18, the day it was asked for. **Status 2026-11-18 (second patch): agreed with the owner; decisions D1221–D1226 written. Nothing in
`web/` is changed yet.** The mock-ups are `notes/mockups/object-interaction-states.svg` (what a person sees and
can do, in all three apps) and `notes/mockups/object-interaction-architecture.svg` (where the code goes, and why). No
decision-log entries are written here: the proposals under "Decisions to write" become decisions once the screens are
agreed, in the id range the owner hands out for the work.

## The ask

> We need to clarify what actions can be done to an object with mouse or keyboard, since the UI is now broken in
> composes because of all the new feature work. Left click selects; the anchor can be dragged in all three apps and is
> repositioned on release; every object can be scaled and rotated in every app. Right click selects the object and opens
> its context menu; it never passes through to the page or the cells below. Tables and objects in composes are especially
> broken; computes passes a right click through to the cells. Creates behaves as intended and is the basis. Fix with
> consistency in architecture and behaviour, and add E2E tests for all of these actions so every new feature checks them.

Answers of the same day (the owner, 2026-11-18):

1. **Stack order** (D1222). Text and cells are always at the bottom of the stack. An object lies over them, so a click on
   it simply selects it; to reach what is under it, move the object. The one exception is composes' wrap *behind the text*
   (D1061), where words are above the object: there, and only there, **Ctrl+click** takes the object (D1063 stays for
   exactly that case).
2. **Tables** (D1224) are in-flow objects: select, move between paragraphs, scale the width, no rotation. The faint frame
   is always on for now. `Esc` in a cell leaves the table completely.
3. **Holding** (D1223): all three apps hold a selected object, as creates does (D82).
4. **Words round a turned object** (D1226): the bounding box.
5. **Menus** (D1225): the object menu is the one the menus workbook v4 (`claudia-menus-4.xlsx`, Context menus) sets, with
   the answers below. This replaces the first proposal of this note (90° entries, no grid entry outside creates).
6. **Table menu:** Name & describe…, Table options…, Merge cells, Split cell, Sort ▸, Delete table (the commands Edit no
   longer has). **Rotate by…** is not offered for a chart or a table. **Wrap text…** is a submenu of the four modes of
   D1061 with a checkmark and *Gap…*, key Ctrl+Alt+R. **Edit text** is in all three apps.
7. **Target branch** `object-interaction`; decision ids D1221–D1240.

## The contract

One table, three apps. The first column is what a person does; creates is the reference, and every cell of the other two
columns that differs from creates is a bug or a stated adaptation.

| Gesture | Contract (all apps) | creates | computes | composes |
|---|---|---|---|---|
| Left press on an object | Selects it, shows the frame, handles and the rotate handle; the press goes to no cell, paragraph or object below | built | selects, no handles | selects, one corner handle |
| Press and move more than 3 screen px | Moves it. The frame follows the pointer as a local preview; one command is sent on release (D82); `Esc` while dragging puts it back | built | built for the anchor, snaps to cell edges, no frame preview | **missing** |
| Release | The anchor is repositioned by the app's rule (below) | slide x/y, grid if the object snaps | the cell under the object's top left | the paragraph and character nearest the drop, plus the offset (D1023) |
| Drag a corner or edge handle | Scales; preview, one command on release; an object that keeps an aspect (image, shape with `aspect`) shows corner handles only and keeps it, so the server never has to refuse | built | **missing** | one corner, no aspect: the server refuses an image's resize, so the size snaps back |
| Drag the turn handle | Rotates about the centre, 3° snap near axes, Shift 15°, Alt free (D1024) | built | **missing** | **missing** |
| Right press on an object | Selects it and opens the object menu at the pointer; the browser's menu, the paragraph menu, the cell menu and the row/column menu do not appear | built | **opens the cell menu** | **opens the paragraph style menu** |
| Right press elsewhere | The app's own menu (cells, headers, paragraphs) as today; Shift+right button still gives the browser's menu there | built | built | built |
| Double click, `Enter`, `F2` | Writes in a text box, a shape or a rendered container; a picture or a chart has no words (D1225) | built | rendered only | rendered only |
| `Delete` | Removes the selected object | built | built | built |
| Arrow keys | Nudge the object (Shift: larger steps; the exact steps are for the shared module to fix). In composes up/down hang it from the previous or next paragraph, left/right change the offset by 10, with Shift by 1 (D1390) | built | **missing** | partly |
| `Esc` | Drops a drag or a turn in progress; otherwise deselects; in a table cell it leaves the table for the text (D1224) | built | deselects | deselects |
| Press elsewhere | Deselects | built | built | built |
| `Tab`, Edit ▸ Select Next Object, Ctrl+Alt+PageUp/Down | Steps through the objects of the page, sheet or slide, so everything above works without a pointer (BITV) | to be checked | PageUp/Down only | Select Next Object |

"Elsewhere" for a keyboard user means the same: nothing in this table needs a pointer.

## Where the code stands (found by reading, not by running: see "What I could not do")

**composes**

- `TextObjectLayer.vue` draws **every** object in `state.objects`, including those of kind `table`. A table (D1201) is an
  object whose definition the kernel holds, and `TableView.vue` already draws it in the flow. So a table has *two*
  bodies on screen: the real one in the flow and an empty box of the object's stored `w × h` hung at its anchor. That
  box is the dark-violet frame in the bug report. It has `pointer-events: auto` and `z-index: 2`, so it lies **over**
  the table's caption: the click on "Options…" lands on the phantom object (which selects it and does nothing), not
  on the button (`web/app/components/TextObjectLayer.vue:79-89`, `TableView.vue:146`). This is one cause of three
  symptoms: the two frames, the dead button, and "I cannot drag the table" (the phantom has no drag either).
- The layer has no move at all: `select` on press, one `.grip` at the bottom right that calls `resizedBy` with no
  aspect. Images keep an aspect (`_check_image_visual`), so the server refuses a free resize and the size snaps back.
- No `contextmenu` handler in the layer; `TextEditor.vue`'s capture handler (`onContextMenu`, line ~571) takes every
  right click in the scroller and opens the paragraph style menu.
- No turn handle.
- The table's borders: the default look (`rules`) draws only the header rules, so the table's start and end are not
  visible while editing.
- A rendered container keeps no fixed aspect (`_check_rendered_visual`), which is why "containers with LaTeX scale
  properly". Their *initial* size is too large: the place that sets it still has to be found (open point 1).

**computes**

- `SheetGrid.vue` has move (mouse events, to the cell) and nothing else: no handles, no turn, no menu. Its
  `@contextmenu.capture="onHeaderContext"` is bound on the viewport, so the cell and header menus take the right click
  that an object should have kept.
- Uses `mousedown`/`mousemove` where creates uses pointer events with capture, so touch and pen behave differently.

**creates** (`SlideCanvas.vue`) is the reference. Its geometry (`geometry.ts`, `turning.ts`) is written for the slide:
the bounds are `SLIDE_W × SLIDE_H` and the unit is slide units. That is why the other apps could not simply reuse it.

## The design: write the gesture once, adapt the anchor

D177 already did this for the model: an object is a **shared body plus an app-specific anchor**, everything but the
anchor in `claudia_core`. The client has the same split waiting to be made. (Diagram: `object-interaction-architecture.svg`.)

**Shared, written once (web/app/lib, pure, with vitest):**

- `object-gestures.ts`: the state machine press → (threshold) → drag | handle | turn → release | cancel. It knows
  *pointer positions in the host's units*, the frame at the start, the bounds, the grid step and the aspect, and it
  returns the preview frame and, on release, one `Commit` (`move`, `resize`, `turn`) or nothing. It reuses
  `moveFrame`, `resizeFrame`, `moveTurned`, `resizeTurned` and `turnFromPointer` (today in `geometry.ts`/`turning.ts`),
  which gain an explicit `Bounds` instead of the constants `SLIDE_W`/`SLIDE_H`. Creates passes the slide as bounds.
- `object-menu.ts` (exists): the item list. Built from the object's kind and two flags (grid, wrap), with the list of D1225 and the table menu of D1224. One list, one order, one key per item (D321, D361).
- `ObjectFrame.vue` (new): the selection outline, the eight (or four) handles and the turn handle with their
  accessible names, drawn once for all three apps; creates' markup moves into it.
- `useObjectInteraction(host)` (new composable): wires `object-gestures` to pointer events with capture, the object
  menu, the key bindings of the contract, and the focus rules. It owns the rule "the press never reaches what is
  below" (`stopPropagation` on the object, `preventDefault` on its `contextmenu`).

**Per app, small, behind one interface `ObjectHost`:**

| `ObjectHost` member (as built, `web/app/lib/object-interaction.ts`) | creates | computes | composes |
|---|---|---|---|
| `toUnits(event)` | slide units | sheet px | page px |
| `subject(id)`: frame, angle, aspect, grid | slide frame; shape aspect or image ratio; 50 units if the object snaps | the cell's top left plus `w × h`; image ratio; no grid | the character's spot plus offset (`floatBox`); image ratio; no grid |
| `bounds` | the slide | the sheet's used area | the text column and the page |
| `scale`, `readonly` | screen scale; look-only | the same | the same |
| `commit(change)`: one `move`, `resize` or `rotate` | `move_object(x, y)`, `resize_object`, `rotate_object` | `move_object(row, col)` and the same two | `move_object(block, offset, dx, dy)` and the same two |

A new app, or a new kind of object, touches the host and nothing else. That is the consistency the owner asked for, in
code as well as in behaviour.

### What each app does on release

- **creates:** unchanged.
- **computes:** the anchor becomes the cell under the object's top-left corner; the object keeps its own `w × h` (it
  never resizes on a structural edit, E6.17). The preview moves freely and snaps to the cell on release.
- **composes:** the anchor becomes the paragraph and character nearest the drop point, and `dx`/`dy` the remainder (the
  free offset of D1023). Dropping on another page or column re-hangs it from that paragraph. A turned object is judged
  by its outline, as in creates (D1022); the words go round its bounding box (D1226).

### Tables (D1201)

A table is an object of kind `table`, drawn once, in the flow. The layer stops drawing objects of kind `table`
(`kind !== 'table'` in `placed`); `TableView.vue` is the only body.

- **Selecting.** A click on the table's name tab (a small tab above its top-left corner, "Table 1", with a grip) or on its
  frame selects the table: one outline, in the table's own box, with a handle on the right edge. A click in a cell puts
  the caret in that cell and does *not* select the table. `Options…` stays on the tab as
  a button above the outline, outside the layer, so nothing covers it, and is also in the table menu.
- **Moving.** Dragging the tab or the selected frame moves the table: a horizontal *drop line* shows between the
  paragraphs it would land after; on release it is one `move_object`. The anchor is a paragraph, so the table never
  floats.
- **Scaling.** The right-edge handle sets the table's width in hundredths of a percent of the column (`TableInfo.width`,
  already stored), shows the percentage while dragging, and snaps to 100 %. Height is the layout's (the kernel says `h`
  is only what was last found), so there is no bottom handle. No rotation: the turn handle and Rotate entries are not
  shown for a table.
- **Right click** on the tab, the frame or inside a cell selects the table and opens the table menu (D1224): *Name &
  describe…, Table options…, Merge cells, Split cell, Sort ▸, Delete table*. Edit no longer carries these (menus
  workbook v4), so the workbook needs these rows added to its Context menus sheet (see "For the workbook" below).
  Insert/delete ▸ and Height/width… belong to the row and column headers; composes' tables have no header UI yet.
- **Borders.** In the editor a table always shows a faint hairline frame and cell lines (a *non-printing editing aid*,
  like Word's gridlines), whatever its look. A look with real rules draws them on top; print and PDF show only the look.
  It may become a View switch when the menu structure has one (D1224).

### The object menu (D1225)

One list in all three apps, in the workbook's order and groups (Context menus rows 1–9):

1. **Name & describe…** (Ctrl+Alt+D) · **Edit text** (Enter; not for a picture or a chart) · **Style…** (Ctrl+Alt+A; for a
   picture it also holds what "Properties" did) · **Rotate by…** (Ctrl+Shift+Alt+Z; not for a chart or a table) ·
   **Wrap text… ▸** (composes only)
2. **Cut**, **Copy** (pictures only)
3. **Release from grid** (creates only; swaps with "Snap to grid") · **Delete** (Del)

No 90° entries; Rotate by… does them. **Wrap text…** is a submenu: ✓ Over the text, Around the object, Above and below the
object, Behind the text, then Gap…; it shows Ctrl+Alt+R, which keeps cycling (D1064). The list is built in `object-menu.ts`
from the object's kind and two flags (grid, wrap), so the apps cannot drift. A chart's menu is the same minus Rotate by…
and Edit text.

## E2E tests: one spec, three apps, every kind

`web/e2e/objects.cjs`, run as `npm run e2e:objects`, parameterised by app (`--model` of the server, as `composes.cjs`
does). It creates one object of every kind the app offers and runs the contract's rows against each:

1. press selects, shows the frame, deselects on a press elsewhere, **and no cell or paragraph below received the press**
   (the caret / active cell did not move);
2. drag moves, with the preview during the move and one history entry after; `Esc` mid-drag restores;
3. each handle scales; an image keeps its ratio (and the size does **not** snap back); a table scales its width only;
4. the turn handle rotates; Rotate by… from the menu (and no Rotate entry for a chart or a table; built in D1232: `rotate-menu.ts`, server refuses a table);
5. right press selects and opens the object menu with exactly the contract's items; the cell menu, the header menu and
   the paragraph menu are **not** in the DOM;
6. keyboard: Tab / Select Next Object reaches the object, arrows nudge, Delete removes, Enter edits;
7. composes: a table's `Options…` opens the dialog; the table has exactly one frame (`[data-testid=object-frame]`
   count is 1); dropping a table between two paragraphs changes the order; the wrap-behind exception needs Ctrl+click;
   `Esc` in a cell leaves the table for the text;
8. a second window sees the holder's outline and name tag while the object is selected, and no drag live, only its result
   (D1223).

A second, cheap guard keeps it honest as features arrive: `tests/test_object_kinds_agree.py` already pins that the kinds
have one list (`claudia_core.OBJECT_KINDS`); it gains one check that every kind of that list appears in
`web/e2e/objects.cjs`'s kind table, so a new kind cannot ship without its row. The same file lists `ObjectHost` members, so a new host member fails a unit test until the
three adapters have it.

## For the workbook (`claudia-menus`), to settle with the other agent

1. **Table context menu rows** (Context menus sheet, Table): add *Table options…, Merge cells, Split cell, Sort ▸, Delete
   table* for composes (D1224). The sheet has only Name & describe….
2. **Rotate by…** row: note "not for a chart or a table" (D1021).
3. **Wrap text…** row: the options are the four modes plus Gap…, key Ctrl+Alt+R (today's `format.wrap-text`, which is
   already in the composes manifest on `main`); the sheet's guess ("In line with text", "No wrap") does not exist in the
   model. "To decide" #16 and #20 are answered by D1225.
4. **Edit text** row: D/E/F = 1 is right; its Enter key is handled by the document view.
5. **Name & describe…** (#12, still "discuss"): not decided here. This work calls the existing dialog for objects; the
   dialog's name and description/note fields for other things follow your answer to #12.

## Open points

1. ~~The initial size of a rendered container~~ — answered 2026-11-19 (D1229): the smaller of 420 × 240 and the rendered
   picture, for containers (the server's `fit`, `claudia_server/rendered.py`) and for imported pictures (`pictureSize` in
   `web/app/lib/images.ts`).
2. **Composes tables have no row and column headers**, so "Height / width…" and "Insert / delete ▸" on headers (workbook
   rows 18, 19) need that UI first; it is not part of this work.
3. **Keys of the table menu entries** stay those they have today (the entries moved from Edit to Tools, D1229).

## Build order

Each patch assumes the earlier ones are applied; the last step of each is a merge of the latest `main`.

1. **This patch:** the note and the two mock-ups.
2. **Shared module — built:** `web/app/lib/object-gestures.ts` (the state machine), `web/app/lib/object-interaction.ts`
   (`ObjectHost` and the composable), an explicit `Bounds` in `web/app/lib/geometry.ts` and `web/app/lib/turning.ts`, the
   object menu of D1225 in `lib/object-menu.ts` (since 2026-11 the definition's object menu, D1644) (with submenus and ticks in `web/app/components/ContextMenu.vue`),
   all with vitest, and creates (`web/app/components/SlideCanvas.vue`) moved onto it with its behaviour unchanged except
   that Esc now drops a drag in progress (D1227). `ObjectFrame.vue` (outline and handles drawn once) is **not** in this
   patch: it moves out of creates when composes is its second user (patch 3 below), where its markup can be checked
   against two apps at once.
3. **composes — built (D1228):** the layer no longer draws tables (`web/app/components/TextObjectLayer.vue`), the table has its
   faint frame, name tab, drag with a drop line and menu (`web/app/components/TableView.vue`), objects are dragged, sized
   with the aspect kept, turned and menued through the shared module (`web/app/lib/text-object-host.ts` turns a drop into the
   paragraph and offset), the right button never reaches the words (`web/app/components/TextEditor.vue`), the object menu and
   its dialogs are in `web/app/components/TextObjectMenu.vue`, and `web/app/components/ObjectFrame.vue` is the handles for
   creates and composes. **Not built:** the table's width handle (a table's width is set in its options); the
   bounding-box wrap of a turned object (D1226); (Edit text for a text box or shape in a text is built, D1232: `set_text`/`write_words` live in `shape_methods`, the editor is `ParagraphEditor.vue` in `TextObjectLayer.vue`.)
   Follow-up of 2026-11-19 (D1229): the size cap, the table commands in Tools (`clients/contract/src/claudia_menus/manifest.py`),
   the workbook's wording, Delete on a selected table, and the object clipboard for pictures in all three apps
   (`web/app/lib/object-clipboard.ts`).
4. **computes — built (D1230):** the host (`web/app/lib/sheet-object-host.ts`: nearest cell on release, one cell per arrow), handles,
   turn handle, *Rotate by…*, the object menu and the `contextmenu` rule in `web/app/components/SheetGrid.vue` (the viewport's
   capture handler now yields to `[data-object]`), pointer events with capture, the picture clipboard pasting into the selected
   cell. **Not built:** wrap and *Release from grid* (do not apply in a cell grid).
5. **`objects.cjs` — written (D1231), not yet run:** `web/e2e/objects.cjs` with its guard test (`tests/test_object_kinds_agree.py`),
   wired into `npm run e2e:objects` and the CI job as the other specs are. Its first run on a machine with a browser is the proof.

## What I could not do here

The sandbox this was written in has no browser (the Playwright download host is blocked), so **no E2E spec could be
run and the symptoms were not reproduced on screen**: the root causes above are from reading the code and fit the
screenshot (the violet box has the size and place of a floating object at the table's anchor and covers the "Options…"
chip). The first run of `objects.cjs` on your machine is the proof.
