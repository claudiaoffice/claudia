# Rotation in the three apps (D1021–D1024)

Branch `rotation-ui`. The owner's ask: UI for rotating objects in all three apps, and — for composes — the object
layer on which objects float. Mock-ups and the open questions are in `notes/rotation-ui-and-the-composes-object-layer.md`
and `notes/mockups/rotation-*`; the owner's four answers (free offset in model and UI, keep Z, charts do not turn,
nudge back in) are what this round built to.

## What the shape of it is

A turn is **one `RotateObject` command** (`core.RotateObject`, D1021), made by `ObjectModel.turn_command`. It carries the
new rotation (whole degrees, clockwise, 0–359, about the frame's centre) and the final anchor when the turn had to move
the object. The anchor stays the *unturned* frame's top left, so the stored geometry is the same whatever the angle.
`turn_command` refuses a chart (kind `diagram`); the command itself does not, so a log written before the rule still
replays.

```
claudia_core.turning      SINE_MILLIONTHS, turned_extent, nudge_into          integer maths, D910
claudia_core.objects      ObjectModel.turn_command                            the one place that makes the command
claudia_creates.model     check_anchor judges the outline (D1022)             0.13.0, breaking
claudia_composes.anchors  BlockAnchor(block, offset, dx, dy)                  D1023, 0.10.0
```

The server has one `rotate_object` method per app; the web client's `lib/turning.ts` mirrors the maths (angle from
the pointer, snapping, `parseAngle`, `QUICK_TURNS`) and its tests pin the same numbers as core's.

## Import and export

OOXML `a:xfrm rot` is in 60 000ths of a degree, clockwise. ODF writes `draw:transform="rotate(-θ) translate(X Y)"`,
X and Y being where the *turned* frame's top left lands, which is why `odp.py` undoes the turn about the centre to get
the anchor back. `claudia_odf_io.splice.set_attributes` gained `remove=` for this. The ODP round trip was checked
against a real LibreOffice, not only against our own reader.

## Menus and keys

Menus come from the manifest in `claudia_shell_gtk.manifest`; `scripts/generate_keys.py` and the two
`generate_menu.py --all` runs turn it into the web key table, the shortcut note and the macOS and Windows menu JSON.
Nothing is hand-copied. Rotate By… is Ctrl+Alt+Shift+Z because Ctrl+Alt+Z is Replay History's (D1024).

## Not done, in the order it matters

1. **Composes' object layer in the web editor** and the layout engine's flow around a free, turned object (E9.29).
2. **Computes' web grid** draws and turns a turned object (E6.17); Rotate is not in its menu until then.
3. **docx, odt, xlsx, ods**: dx/dy and rotation.
4. **Print and preview of turned composes objects** and the D907 margin check.
5. Loss texts for `turn` (pptx) and `off-slide-object` (odp).
6. The ODP/PPTX turning maths ignores anisotropic slide units (a deck whose x and y scales differ).
7. Print of a turned *slide* object relies on the layout engine's existing rotation drawing; nobody has looked at a
   printed page yet.

## How it was checked

Core, creates, composes, both IO packages and the web (vitest) have tests, written first, and pass. **The server tests
were written but could not be run where this was authored; mypy, vulture, the coverage floors and a browser run of
`SlideCanvas.vue` were not done either.** Run them before merging.
