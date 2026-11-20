# Leaving a table, resizing in composes, the sizes of new objects (D1330–D1334, branch `fix-table-exit-object-sizes`)

Three bugs the owner met in composes on 2026-11-20, and what the decisions D1330–D1334 made of them. Specs:
`specs/composes/tables.feature` (the rules "leaving a table", "a table at the end of the text", "the words around a
table") and `specs/objects/new-object-sizes.feature`.

## B5: the caret could not get past a table (D1330, D1331)

**Cause.** A table's boxes are fields of their own (D1213). Their arrow keys moved between boxes and did nothing at the
edge; Esc went back to where the caret was *before* the table. A table at the end of the text has no paragraph after
it, and an ordinary Enter at the end of its paragraph carries the table along (`SplitBlock.follow` moves what hangs at
the cut), so there was nowhere to write.

**Kernel.** `SplitBlock.keep`: what hangs exactly at the cut stays in the paragraph that is cut (a zero-length span at
the offset; a selection starting there still moves). Written to the log only when set. `JoinBlocks.apply` gives back a
split that keeps when the joined paragraph had no objects, so that undo and redo of the new paragraph leave the table
where it was (tested in `test_text_objects_follow.py`). This also changes the undo of an ordinary Backspace-join next
to an object at the end of a paragraph: the object now stays with the first paragraph, which is where it was before
the join.

**Server.** `add_paragraph_after` (`block`): an empty paragraph after the paragraph and what hangs from its end, in the
style Enter at its end would give and with a name, as Enter makes one (D1310). Content domain (D1261).

**Client.** `lib/tables.ts` `leaveSide` says whether a step leaves a table and to which side; `lib/table-path.ts` says
where the caret lands (the next table of the same paragraph, the next paragraph, or a paragraph still to be made) and
which table the words lead into. `TableView` emits `exit` after the box's words are in, and exposes `enter('first' |
'lastRow' | 'lastBox')`. `TextEditor` keeps the table views by object id, hands the caret over, catches Down on the last
line, Up on the first line, Backspace at the start of a paragraph after a table and Ctrl+End when the text ends with a
table, and draws a strip (`data-testid=after-tables`, hidden from screen readers) below a table that ends the text, where
a click writes after it. `TextSession.addParagraphAfter` puts the caret into the new paragraph.

## B6: no object could be resized in composes

**Cause.** `resizeFrame` rounded only the dragged edge. Composes measures an object's frame on the page in fractions of
a pixel, so the width was fractional (`300.1875`), and the server refuses that ("w must be an integer"): the frame
followed the pointer and jumped back. Creates and computes keep whole-unit frames and were not hit.

**Fix.** The size is rounded; the edge that is not dragged keeps its exact place, the dragged one follows the whole size
(so that composes does not see a move that did not happen). Tests in `web/tests/geometry.test.ts`.

## The size of a new picture or container (D1332, D1333, D1334)

**What happened.** XeLaTeX draws `E = mc^2` 43 × 12. The first picture was fitted with the 20 units of every object per
side: 43 × 20, the formula letterboxed 12 high, and the type label "LaTeX" covered it. Measured in a browser on
2026-11-20, before and after: 43 × 20 → 72 × 20.

**Kernel.** `claudia_core.sizing`: `new_object_size` (the most, then the least, then the room, then the smallest of every
object, always with the picture's proportions; the width is made from the height so that a picture passes the aspect
check within one unit) and `font_size_px`. `ObjectModel.least_new_size()` reads the font size of `body_text_style`
(composes `body`, the others `body-text`); `room_for_new_object(anchor)` is the page's text column in composes and the
rest of the slide in creates, no limit on a sheet.

**Server.** The first picture of a container added with `fit` is sized by it (`RenderDesk.render_into`); `add_image`
takes `fit` and sizes a picture from a file the same way. A picture from the object clipboard is pasted without `fit`
and keeps its size.

**Clients.** The three apps send `fit` for a picture from a file. Creates asks for 420 × 240 for a container
(`insertFrame('container', …)`) instead of its 427 × 240 picture frame. Composes sends a new container with the wrap
"above and below" (D1334). `RenderedFace` draws the type label only while there is no picture, or under the pointer.

## Also in this branch

`web/e2e/objects.cjs`: with nothing selected, Format ▸ Rotate is now off as a whole; the check accepts that as well as
three entries that are off.

## Assumptions

- Changes to the Python API are listed under "Unreleased" in the changelogs and the snapshots are regenerated, without
  raising `__version__`, as the branches before this one did.
- "The body text" is the body text *style* of the document; a paragraph with direct overrides does not count.
- The strip below a table at the end of the text is three lines high and invisible; the keys reach the same place.
- With a picture, the type label of a container shows on hover only (also for keyboard users, who do not see it once
  the container has a picture; the description is what a screen reader reads).

## What could not be run

- The LaTeX scenario of the spec skips on the standard E2E server, which has no Latin Modern font; it was checked in
  a browser against a server given the font from the system's TeX installation (72 × 20, label hidden).
- `web/e2e/objects.cjs` still fails in all three apps, after this fix, for reasons that are the app's and not stale
  test code (reported as bugs): in creates, Enter in the Rotate by… field is taken by the slide (it starts writing in the
  text box) and the angle is not applied; in computes, step 5 (turning a picture) times out waiting for the turn handle, cause not looked into; in
  composes, a press on a text box changes the caret in the words below it. Steps 1–4, including the handles, pass in
  computes and creates.
- The GTK, Windows and macOS shells were not started; they show the same web app.
