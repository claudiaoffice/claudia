# pptx import/edit/export, and a second format in the test-document library (D179)

Follows D177's docx design, for pptx: `claudia_creates_io.pptx_to_slides` imports, `apply_edits_to_pptx` closes the
loop by patching an edit back onto the original bytes. The implementation note for D177 explains the general
shape of the problem (why model-state diffing beat command replay, why a retained original blob beat reopening a
path); this note is about what pptx's own structure changes.

## Per-slide parts change the `reconcile` story

docx has one big part (`word/document.xml`) holding every paragraph, so `apply_edits_to_docx` always declares
that one part owned, whatever it actually touched. pptx keeps each slide in its own part
(`ppt/slides/slideN.xml`), confirmed empirically before writing any code (the same discipline D177 used for
docx's own save-behaviour surprise): building a three-slide deck with a table on one slide and a picture on
another, editing one slide's text box and resaving with python-pptx leaves every other slide, every slide layout
and master, the theme, table styles and the picture's own media part byte-identical, untouched by `save()`
itself. `apply_edits_to_pptx` takes advantage of this directly -- the parts it tells `reconcile` claudia owns are
computed fresh each call, from exactly the slides an edit actually reaches (resolved through
`ppt/presentation.xml` and its relationships, reusing `add_transition`'s own `_slide_part` helper), not one fixed
part declared once. `reconcile` is kept anyway, as the same defensive stance D177 took: nothing here should
depend on a library's `save()` happening to leave other parts alone, even when, empirically, it does.

## What becomes an object, and what does not

A text box or one of the three built-in autoshapes (circle, rectangle, triangle -- `shapes.py`'s own builtin
library) becomes a `SlideObject`; anything else on a slide -- a table, a picture, a chart, a group, an autoshape
outside the three built-in ones -- is simply not added, the same "invisible, not wrong" stance `docx_to_text`
takes toward a table. `_classify`/`_modeled_shape_indices` are shared by both `pptx_to_slides` and
`apply_edits_to_pptx`, specifically to avoid a side-channel index: `apply_edits_to_pptx` never trusts "the nth
object on this slide" to mean "the nth shape in `slide.shapes`" (which would be wrong the moment a table or
picture sits between two modeled shapes) -- it rescans the same original bytes with the same classification rule
and zips the result against `baseline.objects_on(slide)`, which is safe because both were produced from the same
file by the same rule.

A picture is deliberately not imported as claudia's own "image" object kind, even though `SlideModel`/
`SlideObject` already have one (`model.py`'s `OBJECT_KINDS`): `slides_to_pptx` cannot export an image yet either
(the model.py and pptx.py module docstrings both already say so), so importing one would have nothing symmetrical
to round-trip through -- it would import, then silently fail to re-export on any edit to its own slide. It stays
beyond-claudia content, same footing as a table, until E10.4/E10.8 give images a real export path.

Style cannot be recovered on import the way docx's named Word styles let `docx_to_text` map back: `slides_to_pptx`
writes literal run-level font size/color, not a named style a reader could echo back. Every reimported text box
becomes `"body-text"` and every autoshape `"plain-shape"` -- the same two styles `slides_to_pptx` itself falls
back to for an object whose style id is not a built-in one.

## Scope of `apply_edits_to_pptx`

Supported: moving, resizing, retexting or restyling an *existing* object. `UnsupportedEdit` for:

- adding, removing or reordering a slide;
- adding or removing an object;
- reordering the objects on a slide -- stacking order lives in `SlideModel._stack`, not on any one object, so a
  per-object `baseline`/`current` diff cannot see a pure reorder at all; this is checked explicitly (comparing
  each slide's `objects_on` order) rather than silently doing nothing, which is what would otherwise happen;
- changing an object's kind (text/shape) or its shape outline (which autoshape it is) -- recreating the
  underlying pptx shape from scratch is a different problem from patching the one that is already there.

## The test-document library's second format

`claudia_test_documents.adapters.ADAPTERS["pptx"]` is now registered (`claudia-creates`/`claudia-creates-io` added
to that package's own dependencies). Three fixtures, mirroring docx's own split:

- `shapes-and-text` (Tier 1) -- a text box and both a circle and a rectangle, across two slides; editing one
  object's text and moving/resizing another leaves everything else alone. Built with explicit EMU coordinates at
  the same 7620-EMU-per-unit scale `claudia_creates_io.pptx` itself uses (`12_192_000 / 1600 ==
  6_858_000 / 900`, both exact), so position/size round-trip with no rounding drift to account for in the
  assertions.
- `beyond-claudia/table` (Tier 2, element-level) -- a table on the *same* slide as the edited text box, so its
  survival depends on python-pptx leaving the table's own graphic-frame element alone while the slide part
  itself is reserialized -- the same mechanic docx's own table fixture checks, just one layer further in
  (`preserve_elements` compares the shape's own `_element.xml` before/after).
- `beyond-claudia/image` (Tier 2, part-level) -- a picture on a slide the edit never reaches at all; its own
  part (`ppt/media/image1.png`) must come back byte-for-byte identical (`preserve_parts`).

Not included: an `export_checks`-style fixture, the pptx analogue of docx's tracked-change-suggestion case. The
one claudia-writable, claudia-unreadable pptx feature is `add_transition` (D147) -- but it is a standalone
function outside `apply_edits_to_pptx`'s own flow entirely (it edits already-exported bytes directly), with no
hook in the `Adapter(import_fn, apply_edits_fn)` contract the runner calls through. Giving it one would mean
widening that contract for a single fixture; left out rather than forced in.

## Not done, on purpose

- xlsx/odt/ods/odp still have no adapter -- same position D177/D178 already stated, one format closer.
- No case opts into Tier 3 (`visual`) yet, same reasoning as D178: nothing here has a property only checkable by
  looking at it.
- Groups, templates, layouts and images (E10.4, E10.8) are not modeled by `SlideModel` at all yet, so none of
  this reaches them; they stay beyond-claudia content indefinitely until that work lands.
