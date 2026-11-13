# pptx import/edit/export, and a second format in the test-document library (D219)

Follows D217's docx design, for pptx: `claudia_creates_io.pptx_to_slides` imports, `apply_edits_to_pptx` closes the
loop by patching an edit back onto the original bytes. The implementation note for D217 explains the general
shape of the problem (why model-state diffing beat command replay, why a retained original blob beat reopening a
path); this note is about what pptx's own structure changes.

## Per-slide parts change the `reconcile` story

docx has one big part (`word/document.xml`) holding every paragraph, so `apply_edits_to_docx` always declares
that one part owned, whatever it actually touched. pptx keeps each slide in its own part
(`ppt/slides/slideN.xml`), confirmed empirically before writing any code (the same discipline D217 used for
docx's own save-behaviour surprise): building a three-slide deck with a table on one slide and a picture on
another, editing one slide's text box and resaving with python-pptx leaves every other slide, every slide layout
and master, the theme, table styles and the picture's own media part byte-identical, untouched by `save()`
itself. `apply_edits_to_pptx` takes advantage of this directly -- the parts it tells `reconcile` claudia owns are
computed fresh each call, from exactly the slides an edit actually reaches (resolved through
`ppt/presentation.xml` and its relationships, reusing `add_transition`'s own `_slide_part` helper), not one fixed
part declared once. `reconcile` is kept anyway, as the same defensive stance D217 took: nothing here should
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

- xlsx/odt/ods/odp still have no adapter -- same position D217/D218 already stated, one format closer.
- No case opts into Tier 3 (`visual`) yet, same reasoning as D218: nothing here has a property only checkable by
  looking at it.
- Groups, templates, layouts and images (E10.4, E10.8) are not modeled by `SlideModel` at all yet, so none of
  this reaches them; they stay beyond-claudia content indefinitely until that work lands.

## Repair: rebased onto the shared object layer (E10.16)

This D219 work was built against the `xlsx-docx-pptx-additive-io` branch at `0792bbe`, before the independent
`shapes-n-images` branch's shared-object-layer round (E10.16, see `implementation-notes-shared-object-layer.md`)
landed on `main`. Both merged cleanly at the git level -- they touch non-overlapping lines -- but `main` ended up
with `claudia_creates_io/pptx.py` calling an API that no longer exists: the flat `SlideObject(id, slide, kind, x,
y, w, h, style, text, shape)` constructor, a module-level `Style`/`BUILTIN_STYLES: dict[str, Style]`, and direct
attribute access (`obj.x`, `obj.text`, ...). The owner found this by running `scripts/run_test_documents.py` on a
fresh checkout of `main` and hit an `ImportError` at the top of the traceback.

Fixed in `pptx.py`, `tests/test_pptx.py` and the three pptx fixture `spec.py` files, by porting every object
construction and every field read onto the shape E10.16 actually gave the model:

- `SlideObject(...)` flat construction becomes `VisualObject(ObjectBody(id, kind, w, h, style, paragraph, shape=...,
  rotation=...), SlideAnchor(slide, x, y))` -- `pptx_to_slides` now also reads a shape's rotation into the body
  (E10.16 requires the field to exist; `slides_to_pptx` still does not write one, so a reimport of claudia's own
  export always sees 0, same as before).
- `obj.x`/`.y` move to `obj.anchor.x`/`.y`; `obj.w`/`.h`/`.style`/`.kind`/`.shape` move to `obj.body.w` etc.
- `obj.text` becomes `obj.body.paragraph.text` (E10.17/D181 landed in the same round): a reimported text box or
  shape gets a paragraph via `paragraph_for`, and `apply_edits_to_pptx` writes `body.paragraph.text` into the
  shape's `text_frame` instead of a flat `body.text`.
- `BUILTIN_STYLES.get(style_id)` becomes `current.styles.computed(style_id)` -- the document's own `StyleBook`,
  not a module-level dict -- and the per-object loop now resolves the *object's* style and its *paragraph's* style
  separately (D181's two-styles split), applying `_style_shape`/`_style_text` to each in turn.
- A test or fixture that retexted an object by `dataclasses.replace(obj, text=...)` now does
  `obj.with_body(paragraph=obj.body.paragraph.with_text(new_text, ()).written_by(author))`; one that moved or
  resized it does `dataclasses.replace(obj, anchor=SlideAnchor(...)).with_body(w=..., h=...)` -- the same idiom
  `ResizeObject.apply` itself uses in `claudia_core.objects`.

Two of the three `test-documents/docx/*/spec.py` fixtures (D217/D218's own, not D219's) hit the same wall at
runtime, one step further in: `TextModel.blocks[i].text = "..."` on what is now a frozen `Paragraph` (`Block =
Paragraph`, D181). `scripts/run_test_documents.py` imports every format's adapter up front, so the broken pptx
import had been masking this -- it failed first and the docx cases never got the chance to run and hit their own
break. Fixed by swapping the direct mutation for `model.remove(block_id, 0, len(old_text))` +
`model.insert(block_id, 0, new_text, [Run(len(new_text), None)])`, the same remove/insert the model itself builds
character-level edits from -- `TextModel` exposes no whole-paragraph "set text" the way `creates`' `SetText`
command does, consistent with the module docstring's point that a composes paragraph is edited by span, not set
at once.

All seven catalogue entries (four docx, three pptx) pass `scripts/run_test_documents.py` again, and
`claudia-creates-io`'s 18 pptx tests pass. Gate: ruff, ruff format and ``claudia-creates-io``'s own mypy are clean
after narrowing one `str | None` the import loop introduced (`_classify`'s return type, asserted non-`None` since
the index it is called on already came from `_modeled_shape_indices`, which keeps only classified shapes). Three
gate failures remain, none from this repair and none in a file it touches: the already-documented `D151`/`D160`
decision-log collisions (now joined by `D177`/`D178`/`D179`, for the same reason -- `shapes-n-images` independently
allocated the same numbers; see the numbering note at the end of `decision-log.md`), a `D163` citation in
`web/app/components/ConnectionIndicator.vue`/`web/app/lib/connection.ts` not yet in the log, a pre-existing ruff
import-order finding in `claudia_computes/__init__.py`, and a pre-existing mypy/test mismatch in
`claudia_composes_io/docx.py`/`test_docx.py` over `list[Run]` vs. `tuple[Run, ...]` -- all from the same
`shapes-n-images` round, outside pptx, and not touched here.
