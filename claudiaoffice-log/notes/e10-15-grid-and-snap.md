# Grid and snap — E10.15

Written 2026-11-07, the same day the feature was asked for, mocked up and built, on branch `grid-in-creates` as it
stood at `886f484` (not rebased onto `main`'s later work — `main` has diverged significantly since, see `git diff
--stat origin/main origin/grid-in-creates`, and the owner asked for the patch against the branch as it stood).

## The ask

> I'd like to add a new feature to creates: show a grid, and objects snapable to it. The grid is only a helper tool,
> not part of the slide itself. Whether it's shown should be controlled by a View menu entry, default on, objects
> snap by default. In the context menu for an object I can "release" the object from the snapping.

Not previously in `backlog.md`; added there as E10.15 only once built (D151).

## The two independent things

The grid's own visibility and an object's own snapping are kept deliberately separate, because they have different
owners and different lifetimes:

- **Shown or hidden** is a client-local view preference — `web/app/lib/grid.ts`'s `useGrid()`, localStorage-backed,
  exactly the shape of `lib/theme.ts`'s `useTheme()` for Dark mode. Not document state, never sent to the server,
  never undoable, never shared between colleagues (one person can hide the lines while another keeps them on).
- **Snaps or not** is real, persisted document state on the object itself — `SlideObject.snap` (`bool`, default
  `True`), changed by its own command, `SetSnap`, with its own entry in the document's history ("Snap to grid" /
  "Release from grid"). It keeps applying even while the grid lines are hidden; only releasing the object itself
  turns it off.

A checkbox in the View menu (`SlideWorkspace.vue`'s `view.grid`) controls the first. The object's own context menu
(`object-menu.ts`) controls the second, per object, with a label that swaps depending on the object's current state
— the same device `Edit ▸ Undo <label>` already uses — rather than a checkbox, which would have needed
`ContextMenu.vue` to learn how to draw a tick mark it does not draw today.

## Mock-up and the four open points

A six-panel SVG (`notes/mockups/grid-and-snap.svg`) was agreed before any code, per the project's own "screens
before code" rule. Four points were open after the mock-up and settled by `AskUserQuestion`, each against its own
recommended default, all accepted:

1. **Snap state persists in the document**, with its own history entry — over a client-only guess that forgets on
   reload.
2. **Snapping applies to both move and resize** — over move only.
3. **50 units between grid lines** by default — over 25 or 100. `SLIDE_W` (1600) and `SLIDE_H` (900) both divide
   evenly by it, and the mock-up's own line spacing (13.125 px in a 420 px-wide, 1600-unit panel) was drawn to
   match this exact value.
4. **The context-menu item swaps its label** — over adding a checkbox to `ContextMenu.vue`.

## What snapping does to a resize, exactly

The tricky case is a fixed-aspect object (a circle, an image) dragged by a corner: snapping both width and height
independently to the nearest grid line would, in general, throw the two out of proportion by more than the one
unit the server tolerates (`claudia_creates.ASPECT_TOLERANCE`). `geometry.ts`'s `resizeFrame`/`resizeKeeping`
already reduces a corner drag to one `wanted` value expressed in width units (picking whichever of the two implied
widths moved further, by its own existing logic); grid snapping was added as one extra step on that single value,
with the other dimension still derived from it through the fixed aspect, exactly as before. The free-resize path
(no aspect) snaps each dragged edge independently, since there is no proportion to keep. Both paths snap-then-clamp
(to the slide and to `MIN_SIZE`), so a snap can never push an object off the slide or below its minimum size.

## Built

- **`claudia_creates`** (0.2.0 → 0.3.0, breaking): `SlideObject.snap`; `SetSnap` command; `AddObject.schema` 2 → 3
  with an upcaster backfilling `snap: True` for schema-2 logged data (mirroring the existing image-fields upcaster,
  schema 1 → 2); `SlideModel.state_schema` 3 → 4. New test file `tests/test_grid.py`; `tests/test_slides.py`'s
  existing round-trip, history-label and random-session tests extended to cover it rather than duplicated.
- **`claudia_server`** (0.15.0 → 0.16.0): `set_snap` method (`id`, `snap:bool`), moved to module level alongside
  `move_object`/`resize_object`/`set_text`/`remove_object` (none of the five close over the shape `library`, so
  moving them out, the same way `add_image` already was, kept `creates_methods_with` under ruff's statement-count
  limit instead of adding a lint exception for it).
- **Web**: `lib/grid.ts` (new, `useGrid`); `lib/geometry.ts`'s `moveFrame`/`resizeFrame` take an optional `grid`
  argument, `GRID_SIZE = 50`; `SlideCanvas.vue` draws the grid as a CSS background (no DOM element per line) and
  passes `GRID_SIZE` into the geometry calls only when the dragged object's own `snap` is true; `object-menu.ts`'s
  `contextMenuItems` takes a `setSnap` action and the new swapping-label item; `slide-session.ts`'s `SlideSession`
  gets `setSnap(id, snap)`. A new design token, `--grid` (`tokens.css`): the grid sits on the slide's own canvas,
  which is always white regardless of light or dark mode (`SlideCanvas.vue`'s `.slide { background: #fff }`), so
  this is a flat value rather than a themed one like `--line`.

## Not verified

- **No browser end-to-end run** (no running server + browser in this environment this round, E10.13's existing open
  item about the two-browser CI runner applies here too) — covered instead by `vitest`/`nuxt typecheck` for the web
  side and `pytest` for the model, server and upcaster.
- **No keyboard shortcut** for View ▸ Show grid, left open and consistent with `view.panel`/`view.dark`, which have
  none either; raised with the owner and left as the author's own call absent an answer.
- **Grid spacing is fixed at 50 units**, not a per-document or per-user setting; nobody asked for one yet.
