# Object interaction: one contract for creates, computes and composes

Written 2026-11-18, the day it was asked for. **Status: proposal, screens and diagram first (project rule). Nothing in
`web/` is changed by this patch.** The mock-ups are `notes/mockups/object-interaction-states.svg` (what a person sees and
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

1. **Stack order.** Text and cells are always at the bottom of the stack. An object lies over them, so a click on it
   simply selects it; to reach what is under it, move the object. The one exception is composes' wrap *behind the text*
   (D1061), where words are above the object: there, and only there, **Ctrl+click** takes the object (D1063 stays for
   exactly that case).
2. **Tables** are in-flow objects: select, move between paragraphs, scale the width, no rotation.
3. **Object menu:** the same list in all three apps, **without** "Snap to grid" in composes and computes (they anchor to
   text and to cells, not to a grid).
4. **Target branch:** `object-interaction`.

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
| Double click, `Enter`, `F2` | Writes in a text box, a shape or a rendered container; a picture has no words | built | rendered only | rendered only |
| `Delete` | Removes the selected object | built | built | built |
| Arrow keys | Nudge the object (Shift: larger steps; the exact steps are for the shared module to fix). In composes up/down hang it from the previous or next paragraph (built), left/right change the offset | built (to be checked) | **missing** | partly |
| `Esc` | Drops a drag or a turn in progress; otherwise deselects | built | deselects | deselects |
| Press elsewhere | Deselects | built | built | built |
| `Tab`, Edit ▸ Select Next Object, Ctrl+Alt+PageUp/Down | Steps through the objects of the page, sheet or slide, so everything above works without a pointer (BITV) | to be checked | PageUp/Down only | Select Next Object |

"Elsewhere" for a keyboard user means the same: nothing in this table needs a pointer.

## Where the code stands (found by reading, not by running: see "What I could not do")

**composes**

- `TextContainers.vue` draws **every** object in `state.objects`, including those of kind `table`. A table (D1201) is an
  object whose definition the kernel holds, and `TableView.vue` already draws it in the flow. So a table has *two*
  bodies on screen: the real one in the flow and an empty box of the object's stored `w × h` hung at its anchor. That
  box is the dark-violet frame in the bug report. It has `pointer-events: auto` and `z-index: 2`, so it lies **over**
  the table's caption: the click on "Options…" lands on the phantom object (which selects it and does nothing), not
  on the button (`web/app/components/TextContainers.vue:79-89`, `TableView.vue:146`). This is one cause of three
  symptoms: the two frames, the dead button, and "I cannot drag the table" (the phantom has no drag either).
- The layer has no move at all: `select` on press, one `.grip` at the bottom right that calls `resizedBy` with no
  aspect. Images keep an aspect (`_check_image_visual`), so the server refuses a free resize and the size snaps back.
- No `contextmenu` handler in the layer; `TextEditor.vue`'s capture handler (`onContextMenu`, line ~571) takes every
  right click in the scroller and opens the paragraph style menu.
- No turn handle.
- The table's borders: the default look (`rules`) draws only the header rules, so the table's start and end are not
  visible while editing.
- A rendered container keeps no fixed aspect (`_check_rendered_visual`), which is why "containers with LaTeX scale
  properly". Their *initial* size is too large: the place that sets it still has to be found (open point 4).

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
- `object-menu.ts` (exists): the item list. Gains `snap` as optional so composes and computes leave it off, and `table`
  entries for a table. One list, one order, one key per item (D321, D361).
- `ObjectFrame.vue` (new): the selection outline, the eight (or four) handles and the turn handle with their
  accessible names, drawn once for all three apps; creates' markup moves into it.
- `useObjectInteraction(host)` (new composable): wires `object-gestures` to pointer events with capture, the object
  menu, the key bindings of the contract, and the focus rules. It owns the rule "the press never reaches what is
  below" (`stopPropagation` on the object, `preventDefault` on its `contextmenu`).

**Per app, small, behind one interface `ObjectHost`:**

| `ObjectHost` member | creates | computes | composes |
|---|---|---|---|
| `toUnits(event)` | slide units | sheet px | page px |
| `frameOf(object)` | slide frame | the cell's top left plus `w × h` | the character's spot plus offset (`floatBox`) |
| `bounds()` | the slide | the sheet's used area | the text column and the page |
| `commitMove(id, frame)` | `move_object(x, y)` | `move_object(row, col)` | `move_object(block, offset, dx, dy)` |
| `commitResize`, `commitTurn` | `resize_object`, `rotate_object` | the same | the same |
| `grid()` | 50 units if the object snaps | `null` | `null` |
| `aspectOf(object)` | shape aspect, image ratio | image ratio | image ratio |

A new app, or a new kind of object, touches the host and nothing else. That is the consistency the owner asked for, in
code as well as in behaviour.

### What each app does on release

- **creates:** unchanged.
- **computes:** the anchor becomes the cell under the object's top-left corner; the object keeps its own `w × h` (it
  never resizes on a structural edit, E6.17). The preview moves freely and snaps to the cell on release.
- **composes:** the anchor becomes the paragraph and character nearest the drop point, and `dx`/`dy` the remainder (the
  free offset of D1023). Dropping on another page or column re-hangs it from that paragraph. A turned object is judged
  by its outline, as in creates (D1022); how words flow round a turned object is open point 3.

### Tables (D1201)

A table is an object of kind `table`, drawn once, in the flow. The layer stops drawing objects of kind `table`
(`kind !== 'table'` in `placed`); `TableView.vue` is the only body.

- **Selecting.** A click on the table's name tab (a small tab above its top-left corner, "Table 1", with a grip) or on its
  frame selects the table: one outline, in the table's own box, with a handle on the right edge. A click in a cell puts
  the caret in that cell and does *not* select the table. `Options…` moves into the table's menu and stays on the tab as
  a button above the outline, outside the layer, so nothing covers it.
- **Moving.** Dragging the tab or the selected frame moves the table: a horizontal *drop line* shows between the
  paragraphs it would land after; on release it is one `move_object`. The anchor is a paragraph, so the table never
  floats.
- **Scaling.** The right-edge handle sets the table's width in hundredths of a percent of the column (`TableInfo.width`,
  already stored), shows the percentage while dragging, and snaps to 100 %. Height is the layout's (the kernel says `h`
  is only what was last found), so there is no bottom handle. No rotation: the turn handle and Rotate entries are not
  shown for a table.
- **Right click** on the tab, the frame or inside a cell selects the table and opens the table menu: Row ▸, Column ▸,
  Sort ▸, Merge Cells, Split Cell, Table Options…, then the common part (Style…, Name & describe…, Cut, Copy, Delete).
  These are the Edit menu's table entries, with the same keys (`table-menu.ts`); nothing new is invented.
- **Borders.** In the editor a table always shows a faint hairline frame and cell lines (a *non-printing editing aid*,
  like Word's gridlines), whatever its look. A look with real rules draws them on top; print and PDF show only the look.
  Whether this needs a View switch is open point 5.

### The object menu

Same list in all three apps, in this order: **Style…, Name & describe…** (the label the menu-structure draft gives
"Describe…"), separator; for a picture: **Cut, Copy, Properties**; otherwise **Edit Text**; separator; **Rotate Right 90°, Rotate Left 90°, Rotate By…** (not for a chart or a table); separator;
**Snap to grid** (creates only); separator; **Delete**. A table's menu is the one above. A chart in computes has the same
menu minus the rotate entries. Every item has the key it has in the Edit/Format menus; the shortcut hints are shown.

## E2E tests: one spec, three apps, every kind

`web/e2e/objects.cjs`, run as `npm run e2e:objects`, parameterised by app (`--model` of the server, as `composes.cjs`
does). It creates one object of every kind the app offers and runs the contract's rows against each:

1. press selects, shows the frame, deselects on a press elsewhere, **and no cell or paragraph below received the press**
   (the caret / active cell did not move);
2. drag moves, with the preview during the move and one history entry after; `Esc` mid-drag restores;
3. each handle scales; an image keeps its ratio (and the size does **not** snap back); a table scales its width only;
4. the turn handle rotates; Rotate Right/Left/By… from the menu;
5. right press selects and opens the object menu with exactly the contract's items; the cell menu, the header menu and
   the paragraph menu are **not** in the DOM;
6. keyboard: Tab / Select Next Object reaches the object, arrows nudge, Delete removes, Enter edits;
7. composes: a table's `Options…` opens the dialog; the table has exactly one frame (`[data-testid=object-frame]`
   count is 1); dropping a table between two paragraphs changes the order; the wrap-behind exception needs Ctrl+click.

A second, cheap guard keeps it honest as features arrive: `tests/test_object_kinds_agree.py` already pins that the kinds
have one list (`claudia_core.OBJECT_KINDS`); it gains one check that every kind of that list appears in
`web/e2e/objects.cjs`'s kind table, so a new kind cannot ship without its row. The same file lists `ObjectHost` members, so a new host member fails a unit test until the
three adapters have it.

## Open points (answers wanted before code)

1. **Holding.** Creates holds an object while it is selected (D82: others see an outline and a name). Computes keeps
   its selection local ("not shared", E6.17); composes' `session.selectObject` is shared. Should all three hold, as in
   D82? Proposed: yes, as it is the same story as the lock in creates and E10.6, but it changes what colleagues see in
   computes and composes, so it is yours to say.
2. **The grid in computes and composes.** Nothing snaps there in this proposal (cells and characters are the grid). If
   you would rather have free positioning in computes (an object between two cell edges), that is a new anchor field.
3. **Words round a turned object in composes.** Wrap uses the object's box; creates judges a turned object by its
   outline (D1022). Proposed: the wrap uses the turned object's bounding box, and the exact outline is a later story.
4. **The initial size of a rendered container** (LaTeX) is too large; I have not yet found where it is set. Proposed:
   the container is first drawn at its rendered size (the renderer returns `width × height`, `service.py`), capped at
   the column width, then scaled by the person.
5. **The editing frame of a table.** Always on, or switchable at View ▸ Table gridlines? The menu draft is under
   review, so I would not add a menu entry without your word.
6. **Selecting without a pointer inside a table.** Escape in a cell leaves the table for the text today; proposed:
   a second Escape selects the table (frame and handle), a third gives the caret back.

## Build order

Each patch assumes the earlier ones are applied; the last step of each is a merge of the latest `main`.

1. **This patch:** the note and the two mock-ups.
2. **Shared module** (`object-gestures`, `Bounds` in `geometry`/`turning`, `ObjectFrame`, `useObjectInteraction`,
   `object-menu` changes) with vitest, creates moved onto it with its behaviour unchanged (its e2e stays green).
3. **composes:** stop drawing tables in the layer, table frame/tab/drop line/width handle, host adapter, object menu, the
   `contextmenu` rule in `TextEditor.vue`, aspect lock, turn handle, the LaTeX initial size.
4. **computes:** host adapter, handles, turn, menu, the `contextmenu` rule in `SheetGrid.vue`.
5. **`objects.cjs`** and its guard test, wired into `npm run e2e:objects` and CI as the other specs are.

## What I could not do here

The sandbox this was written in has no browser (the Playwright download host is blocked), so **no E2E spec could be
run and the symptoms were not reproduced on screen**: the root causes above are from reading the code and fit the
screenshot (the violet box has the size and place of a floating object at the table's anchor and covers the "Options…"
chip). The first run of `objects.cjs` on your machine is the proof.
