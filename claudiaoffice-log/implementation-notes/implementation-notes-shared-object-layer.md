# One shared object layer for shapes, images and styles (E10.16, D177–D179)

Branch `shapes-n-images`. The owner's ask, in four bullets: align creates' style system with `claudia_core`; move
the resize/move command and its logic into core; separate an object's anchoring from the properties the three apps
share; and make images objects in all three apps. A fifth thing was named as the *next* round and is deliberately
not here: all the shapes, the text box and the image import available everywhere with identical properties.

## What the shape of it is

An object is now **a body and an anchor**.

```
VisualObject[A]      = ObjectBody + A            (claudia_core.objects)
ObjectBody           = id, kind, w, h, style, text, shape, image, imported, rotation, snap
SlideAnchor          = slide, x, y               (claudia_creates)   kind "slide"
CellAnchor           = sheet, row, col           (claudia_computes)  kind "cell"
BlockAnchor          = block, offset             (claudia_composes)  kind "block"
```

The body is the same dataclass in all three apps. The anchor is the only per-app part, behind a three-member
protocol (`kind`, `container`, `to_data`). `ObjectModel` is the mixin an app's model inherits for the objects, the
per-container stacking order, the shape outlines and the image assets; it leaves `containers()`, `check_anchor`
and `anchor_from_data` to the app and nothing else.

The whole object command family is core's, namespaced `core.*`: `DefineShape`, `ForgetShape`, `DefineImage`,
`ForgetImage`, `AddObject`, `RemoveObject`, `MoveObject`, `ResizeObject`, `RotateObject`, `SetText`, `SetSnap`.
What is left in each app's own `commands.py` is only what that app alone has — creates keeps `AddSlide` and
`RemoveSlide`, computes keeps its cells, structure and line sizes, composes its text and suggestions.

### Why the anchor crosses the wire as plain data

A command must be immutable plain data that `CommandRegistry.build` can rebuild with no model in hand, but only
the app can read its own anchor. So `MoveObject.anchor` is a `dict`, read by `ObjectModel.anchor_from_data` inside
`apply`, where `ctx.model` exists. This is exactly the seam `region_from_data` already was, and it keeps commands
round-tripping byte-for-byte — which an earlier draft holding a real `Anchor` object did not, since a command
built from the log would not have compared equal to one built in the server.

## What stopped being written twice

Before this round these existed once per app, near-identically: `insert_object`, `delete_object`,
`replace_object`, the `_stack` dict, `objects_on`, `check_object`, `_check_visual`, `_check_frame`, the
`DefineImage`/`ForgetImage` pair (line-for-line identical but for the `kind` string), `ObjectSet` and
`ObjectsChanged`. All of them are now in `claudia_core.objects`, once.

`claudia_core.shapes` took the shape *format* — `ShapeDefinition`, `parse_shape`, pure, no I/O, so core stays
I/O-free and all three apps can hold a shape in a document. `ShapeLibrary`, which reads folders from disk, stayed
behind in `claudia_creates.shapes`.

## Styles

creates' styles were a module-level `dict[str, Style]` with its own flat dataclass, read-only, living in the
program rather than the document. They are now core `StyleDef`s in the document's own `StyleBook`, exactly as in
composes: inheritance through `based_on`, the deviation flag `to_name`, resolution through `computed()`, and the
core `CreateStyle`/`ChangeStyle`/`RenameStyle` commands, so a style change is in the log, can be undone and is
seen by everybody. computes gained a style book too, with the same three style ids, since an object needs a style
to look anything up in.

**A bug this uncovered.** creates' built-in styles had never been validated — its own `Style` did no checking at
all — and one font name in `body-text`, `-apple-system`, is in fact refused by `ALLOWED_CSS` (a font name may not
start with a hyphen). Routing the styles through a real `StyleBook` failed on the very first import. The stack is
now the one composes uses.

Shapes say their background and border as `fill`/`stroke`/`stroke-width`, not `background-color`/`border-*`
(D178): a shape is an arbitrary outline in a 100 by 100 box, so the CSS box vocabulary cannot give a circle or a
triangle a border at all. Both were already in `ALLOWED_CSS`; this is a choice of which one shapes use.

## composes, which had no objects at all

It has them now, with `BlockAnchor(block, offset)`: the paragraph and the character the object hangs from. Two
decisions are worth re-reading in D179, because they pull in opposite directions and both are deliberate:

* the object **floats** — the words around it neither wrap beside it nor are pushed down by it. Text wrap is a
  layout feature of its own and is not in this round.
* the anchor **follows the text**, where a `CellAnchor` is frozen on purpose. A sheet anchor must not move when
  somebody inserts a row above it, or the picture leaps across the sheet; a character offset that does *not* move
  points at a different word the moment anybody types. So an anchor moves through other people's edits by the same
  `TextCommand.follow` that cursors, zones and suggestions already use. `join` carries a paragraph's objects into
  the surviving one (`carry_objects`); a split hands the objects past the cut to the new paragraph.

This is the clearest thing in the whole round: the same picture wants frozen coordinates on a sheet and following
ones in a paragraph, and that is precisely why the anchor is the part each app keeps.

## The wire, and the client

An object now travels identically in all three apps —
`{id, kind, w, h, style, text, shape, image, imported, rotation, snap, anchor}` — with only `anchor` differing.
`ObjectSet` and `ObjectsChanged` lost their `slide`/`sheet` field for one `container`.

The web client got the matching split in `web/app/lib/objects.ts`: a shared `ObjectBody`, the `Anchor` union, and
the per-app frame adapter (`slideFrame`/`slideAnchor`). `geometry.ts` already worked purely on a `Frame`, so the
resize and move maths needed no change — only the handful of places that read `o.x` now read the anchor through
`slideFrame(o)`. `SlideCanvas.vue` draws with the style's `computed` CSS rather than its own `css`, which is what
makes inherited styles render correctly.

New server methods: `resize_object` and `rotate_object` for computes (it had neither), and `styles` for computes.
creates gained `rotate_object`.

## Deliberately not done

* **Old logs do not replay.** Renaming the commands' `kind` to `core.*` makes a log written before this round
  unreadable: `CommandRegistry` keys upcasters by `(kind, schema)` and cannot alias one kind to another. The owner
  chose this over adding an aliasing mechanism, this being pre-release (D177). The old `creates.AddObject`
  upcasters for schemas 1 and 2 went with it, and the two tests that covered them now assert the plain error
  instead. If logs ever need to survive such a move, the mechanism to add is a kind alias in `CommandRegistry`.
* **Rotation has no client surface.** The field is persisted and validated (0–359) and `RotateObject` and the two
  server methods exist, but nothing in the UI turns an object yet.
* **A shape's text is still a plain `str`.** Promoting it to the shared paragraph entity — composes' `Block`, with
  its style chain and its authorship runs — is the obvious next move and is what would let a shape carry a real
  paragraph. It needs a per-host overflow policy (a paragraph in a fixed box cannot push anything down), which is
  the same shape of problem the anchor was.
* **Shapes, text boxes and the image import are not yet offered in all three apps.** The model carries them
  everywhere now; what is missing is each app's insert UI. That is the next round the owner named.

## State and schema

creates 4→5, computes 3→4, composes 3→4. A snapshot is only a cache (D15), so these rebuild from the log; it is
the `kind` rename, not the state schema, that breaks old documents.

## Gate

`scripts/check_debt.py`: ruff, ruff format, mypy, vulture, i18n extraction, mo compilation, docs (warnings as
errors), the three performance guards, web tests, web types, the Linux client's mypy and tests — all green.
Python tests 2642 passed. Three known failures, none of them this round's:

* `test_decision_log_never_allocates_a_number_twice` — `D151` and `D160` are each allocated twice on `main`, from
  branches that diverged before either had the other's entries. The log itself already documents this and leaves
  it for a renumbering pass; both numbers are cited across about twenty files, so which decision keeps its number
  is not a patch-level call.
* `test_formula_performance.py::test_opening_from_a_snapshot_is_linear_in_the_formulas` — a marginal timing guard
  (limit 25) that passes three runs in four on a shared container, failing around 25.4. Measured directly, the
  ratio is 19.6, and the only thing this round adds to `WorkbookModel.restore` is a constant 0.04 ms for the style
  book, which *lowers* a ratio rather than raising it.
* `test_check_debt.py::test_ci_catches_the_real_bug_with_no_node_modules` — asserts its own precondition, that
  `web/node_modules` is absent. It fails in any checkout where the web dependencies are installed, which they must
  be to run the web half of the gate at all.
