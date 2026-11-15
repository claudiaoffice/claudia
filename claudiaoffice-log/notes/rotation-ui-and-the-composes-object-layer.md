# Rotation UI in all three apps, and the object layer in composes

Written 2026-11-15, the day it was asked for. **Status 2026-11-15 (end of day): creates is built on `rotation-ui` (D1021–D1024); the composes object layer and the turned objects in computes are not (see `implementation-notes/implementation-notes-rotation.md`). Originally: mock-ups only, nothing is implemented:** the screens come first
(project rule), so this note records the design, what the code has today, what building it would touch, and the open
points that need an answer before any story is started. No decision-log entries are written here; the proposals
below become decisions when the screens are agreed, in the range the owner hands out for the work.

## The ask

> I'd like to have UI for rotation of objects in all three apps. Can you mock some please? In composes, we should
> finally introduce an object layer on top of which objects can float around.

It is also an open line of the 2026-11-14/15 work plan (`human.md`): "rotation UI in all three apps".

## What the code has today

- **The model already turns objects.** `ObjectBody.rotation` is whole degrees, 0–359, validated and persisted; the
  command `core.RotateObject` exists with its inverse (D177). The servers of creates and computes have
  `rotate_object`. Nothing in any client calls it. The shared client type says the same: "Whole degrees clockwise.
  Persisted and validated by the model; no client surface yet" (`web/app/lib/objects.ts`).
- **The geometry is upright only.** `web/app/lib/geometry.ts` moves and resizes a `Frame` (x, y, w, h) and keeps it
  on the slide; it knows no angle.
- **Print and the PDF already turn.** D907 prints floating objects at their anchor; D910 says rotation uses a table
  of sines so that a display list is the same everywhere. The shared drawing is `layout/src/apps/objects.ts`.
- **composes has the model of an object layer and no view of it.** An object hangs from a paragraph and a character
  (`BlockAnchor`, D179), floats over the text without wrap, follows the text through other people's edits, and
  prints where it hangs (D907). D907 says it plainly: "The composes web client does not show floating objects in
  the text yet (they arrive by import)". So "introducing the object layer" is a client and interaction job, with one
  model question (open point 1).
- **Shared rules the design leans on:** holding an object by selecting it (D82), the object's own snap to the grid
  (D214), one style per container's text (D306), Title Case menu labels with the same key in every client (D321,
  D361), the history entry as the unit of undo.

## The design, in one page

Mock-ups, in `notes/mockups/`:

| File | Shows |
|---|---|
| `rotation-handle-menu-popover.svg` / `.png` | The shared parts: handle and its states, the angle chip, Shift and upright snapping, Format ▸ Rotate, the Rotate By… popover, the object's context menu |
| `rotation-creates.svg` / `.png` | A slide with turned objects, an arrow being turned, an object held by someone else, a turn near the slide's edge |
| `rotation-computes.svg` / `.png` | A sheet with a turned arrow and note hanging from cells, rows inserted above, the handle when there is no room above, what is *not* rotation (text in cells) |
| `rotation-composes.svg` / `.png` | The object layer: a text with a stamp and a photo floating over it, the tether to the anchor character, the two layers, text changing above, menus and keys |

**On the canvas.** A held object shows one new thing: a *rotate handle*, a circle with a turning arrow on a stem
30 px above its top edge. Resize handles and the outline turn with the object. Dragging turns it about its centre;
a chip beside the handle reads the angle (0–359, so −20° is shown as 340°); Shift snaps to 15° steps; within 3° of
0°, 90°, 180° or 270° it snaps to upright (Alt switches that off). The turn is local until you let go, then one
command and one history entry ("Rotate object · Arrow 2 · 0° → 340°"), as moves and resizes are (D82).

**In the menus.** Format ▸ Rotate ▸ Rotate Right 90°, Rotate Left 90°, Rotate By…, beside Describe Object…, greyed
unless an object is held, the same in all three apps and in the desktop shells' native menus.

| Entry | Key | Free in all three menus? |
|---|---|---|
| Rotate Right 90° | Ctrl+Alt+. | yes |
| Rotate Left 90° | Ctrl+Alt+, | yes |
| Rotate By… | Ctrl+Shift+Alt+Z | yes (Ctrl+Alt+Z, first drawn here, is Replay History's: corrected 2026-11-15, D1024) |
| Select Next Object (composes, computes) | Ctrl+Alt+Shift+B | yes |

Checked against `menu.creates.json`, `menu.composes.json` and `menu.computes.json` on 2026-11-15. Ctrl+Alt+R would
be the obvious key for Rotate, but computes' Random Generator has it; the free Ctrl+Alt letters left are few, and
E, M and Q are AltGr characters on a German keyboard (€, µ, @), so they would type instead of act on Windows. Comma
and period sit next to M and mean "left" and "right" on a US layout. Ctrl+Alt+Z for Rotate By… was the weak one, and it turned out to be taken
(Replay History); it is Ctrl+Shift+Alt+Z now. If the owner prefers R, Random Generator would have to move.

**Rotate By… popover.** Opens beside the object like Apply Style… (`besideRect` in `geometry.ts`); an angle field
(whole degrees, ↑ ↓ ±1°, Shift ±15°), a dial that is the same turn as the handle, quick buttons (−15°, +15°, 90°,
180°, 270°, Upright), Done and Cancel. Everything previews on the canvas; Enter or Done sends one command, Esc puts
it back.

**The object's context menu** gets the same Rotate submenu with the same keys.

### creates

The handle sits with the existing hold: others see the holder's colour on the turned outline and her name on a tag
that stays upright at the corner of the turned bounding box; they get no handle and the usual refusal if they click.
A turned object is "different from its layout" like a moved one (the dot on the tab, E10.5). The History entry names
the object by its own name.

### computes

A sheet object hangs from a cell (`CellAnchor`, E6.17) and a turn never moves the anchor: the frame's top-left stays
on the anchor cell and the object turns about its own centre. While an object is held the anchor cell is outlined
with a pin and a chip. Inserting a row above moves the object with its cell, keeping size and turn (E6.17). When the
handle would sit under the column headers or a frozen row, the stem and handle go below the object. Text turned
inside a *cell* (an angled column heading) is a cell style, not an object, and has no handle; Format ▸ Rotate stays
greyed on a cell so nobody looks for it there.

### composes: the object layer

A layer over the text that takes the pointer only where an object is: a click on an object holds it, a click
anywhere else is the text's. Esc on a held object puts the caret back at its anchor, Enter edits the words of a text
box. While an object is held the view draws a dashed tether from the frame's top-left corner to a ring on the
character it hangs from, with a chip ("hangs from ¶ 1"); nothing of this shows otherwise, so reading stays quiet.
Turning is about the centre, so the corner and the anchor do not move. The anchor follows the character through
other people's edits (D179), the turn stays. New entries as in the other two apps: Edit ▸ Insert ▸ Text Box
(Ctrl+Alt+B) and Image… (Ctrl+Alt+I), Format ▸ Describe Object… and Rotate, and Edit ▸ Select Next Object so that
the layer is reachable without a mouse (Tab is the list indent in composes). A new object hangs from the character
before the caret, 32 px down and right.

## Open points, each with a recommendation

1. **A free offset from the anchor (composes, needs a model change).** Today an object's top-left sits on the
   character it hangs from (D179, D907), so it cannot float into a margin or beside a paragraph. The mock-up shows
   an offset (dx, dy) from the anchor. *Recommended:* add it to `BlockAnchor`; without it "floating around" means
   "jumping from character to character". It changes the anchor's wire form and D907's placement rule.
2. **Charts do not turn.** *Recommended:* Rotate is greyed for a chart (kind `diagram`); pictures, shapes, text
   boxes and rendered text (D390) do turn.
3. **Must a turned object's outline stay on the slide (creates)?** *Recommended:* yes; a turn that would push a
   corner off nudges the object inward in the same step, one undo. The alternative is to allow overhang and clip in
   the show and in print.
4. **Grid and snap on a turned object (D214).** *Recommended:* moving snaps the turned outline's edges; resizing a
   tilted edge is free, since no grid line runs along it.
5. **Reaching objects by keyboard (composes, computes).** *Recommended:* Edit ▸ Select Next Object, Esc to return.
   Without it the rotate handle is for mouse users only, which BITV 2.0 does not allow (2.1.1). The handle itself is
   focusable with arrow keys.
6. **Opaque objects over words (composes).** No wrap in this round (D179). *Recommended:* a new text box has no
   fill, a picture does; text under an opaque object is simply covered, and printing draws it over the text (D907).
7. **Several objects at once.** Not in this round, there are no groups (E10.6); each object turns about its own
   centre.
8. **Menu shortcut for Rotate By…** See the key table; the owner's call.
9. **Greyed or hidden when nothing is held.** The mock-ups follow today's rule (Describe Object… is greyed). If the
   principle "what is meaningless in the context is not shown" from the work plan is adopted, Rotate follows it with
   no other change.

## What building it would touch

Listed so the story can be sized; none of it is started.

- **Geometry (`web/app/lib/geometry.ts`, pure functions, tested first).** The turned outline of a frame; hit testing
  against it; moving by the turned bounding box; resizing in the object's own axes with the opposite corner fixed on
  the screen; the angle from a pointer, with the Shift and upright snaps; clamping by the outline (open point 3).
  Whole degrees at the model boundary, no `Math.sin` in anything that reaches a display list (D910).
- **Components.** A rotate handle with a real hit area of 32 px and the visible circle of 19 px; the popover with the
  dial; the chip. Colour contrast of the handle and the focus ring is at least 3:1 on any background (BITV 1.4.11).
- **Menus.** The three entries into the shared manifest (`clients/linux/src/claudia_shell_gtk/manifest.py`), the
  generated menus of the macOS and Windows clients, the keys table (`scripts/generate_keys.py` regenerates
  `notes/keyboard-shortcuts.md`) and `web/` menu sources; the test that compares the two (D361) must stay green.
- **Servers.** `rotate_object` exists for creates and computes; composes' server has no object methods beyond the
  read ones D907 added, so it needs add, move, resize, rotate and remove for objects (and `select next` is a view
  matter, not a server one).
- **Import and export (a rule of the project).** OOXML stores rotation in `a:xfrm` as 60 000ths of a degree,
  clockwise; ODF stores it in `draw:transform` in radians and its sign has to be checked against the test documents
  (LibreOffice counts counter-clockwise). Round trips for PPTX, XLSX drawings, DOCX anchored objects, ODP, ODS and
  ODT with turned pictures, shapes and text boxes, using `test-documents/`.
- **Print, PDF, presenter.** The display list already turns objects (D910); the preview must use the turned outline
  for the margin test in composes (D907).
- **i18n.** All labels through the gettext catalog. Proposed German: *Drehen* (Format submenu), *Nach rechts drehen
  (90°)*, *Nach links drehen (90°)*, *Drehen um…*, *Winkel*, *Aufrecht*, *Nächstes Objekt auswählen*, *Objekt
  drehen* (history).
- **Accessibility.** Every way of turning is reachable without the pointer (menu, keys, popover field); the handle is
  focusable and exposes `role="slider"` with 0–359 and a text value "37 degrees clockwise"; a live region says
  "Rotated to 37 degrees"; an object's accessible name adds ", turned 37 degrees" only when it is not upright.
- **Tests first (TDD).** Pure geometry tests (angle from pointer, snaps, turned bounding box, resize in own axes);
  model tests for normalisation (−10 → 350, 360 → 0) and undo; session tests for one history entry per drag; menu
  manifest tests; round-trip tests for each format above; a Firefox end-to-end of the drag (Firefox is the main
  testing browser).

## Not verified

- The mock-ups are drawings, not screens; nobody has tried the handle's size or the 3° snap with a hand on a mouse.
- Whether ODF's `draw:transform` sign is as stated above is from memory of LibreOffice's output and has to be
  checked against a file written by it before any import code is written.
- The proposed keys were checked for collisions in the three manifests only, not against the browsers' and the
  desktop environments' own shortcuts; Ctrl+Alt+, and Ctrl+Alt+. are not known to be taken, which is not the same
  as free.
- The composes mock-up shows an offset from the anchor that the model does not have (open point 1).
