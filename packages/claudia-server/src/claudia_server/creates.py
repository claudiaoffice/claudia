"""The methods of the presentation app: what a slide view needs to show a slide and to take what people do on it.

``creates_methods`` is ``core_methods`` plus ``slides``, ``slide``, ``shapes``, ``styles``, ``add_slide``,
``add_object``, ``move_object``, ``resize_object``, ``set_text`` and ``remove_object``. Positions and sizes are whole
units of the slide space (1600 by 900). A shape is chosen by its id from the server's shape library; the first time a
document uses it, its outline is copied into the document, in the same step of the history as the object, so a
document never depends on the library of the server it is opened on. Every write may carry the ``base`` revision of
the client's view, as ``apply`` does.

``creates_methods_with(library)`` makes the table for a server whose library holds more than the built-in shapes.
"""

from __future__ import annotations

import secrets

from claudia_core import Batch
from claudia_creates import (
    BUILTIN_STYLES,
    AddObject,
    AddSlide,
    DefineShape,
    MoveObject,
    RemoveObject,
    ResizeObject,
    SetText,
    ShapeLibrary,
    SlideModel,
    SlideObject,
)
from claudia_creates.model import OBJECT_KINDS

from .protocol import Context, MethodTable, RequestError, core_methods

STYLE_OF_KIND = {"text": "body-text", "shape": "plain-shape"}


def _deck(ctx: Context) -> SlideModel:
    model = ctx.document.model
    if not isinstance(model, SlideModel):
        raise RequestError("command_error", "this document is not a presentation")
    return model


def _rev(ctx: Context) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _fresh(prefix: str, taken) -> str:
    """An id nobody has used in this document. Ids are random, never counted: the id of a removed object must not come
    back, or undoing its removal would collide with the newcomer."""
    while True:
        candidate = f"{prefix}{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


def _done(ctx: Context, command, base, **extra) -> dict:
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {**extra, "revision": applied.revision.to_data()}


def creates_methods_with(library: ShapeLibrary) -> MethodTable:
    """The method table of presentations on a server whose shape library is ``library``."""
    table = core_methods.extended()

    @table.method("slides")
    def _slides(ctx):
        """The slides in order, each as `{id, objects}` where objects is how many things are on it."""
        deck = _deck(ctx)
        return [{"id": slide, "objects": len(deck.objects_on(slide))} for slide in deck.slides]

    @table.method("slide", "slide:str")
    def _slide(ctx, slide):
        """One slide as `{revision, slide, objects}`: its objects, the one in front last. An object is
        `{id, slide, kind, x, y, w, h, style, text, shape}`."""
        deck = _deck(ctx)
        if slide not in deck.slides:
            raise RequestError("command_error", f"unknown slide {slide!r}")
        return {"revision": _rev(ctx), "slide": slide, "objects": [obj.to_data() for obj in deck.objects_on(slide)]}

    @table.method("shapes")
    def _shapes(ctx):
        """The outlines: `{library, document}`. `library` is what the server offers for insertion, `document` what
        this document has taken in (and what its objects are drawn with). An outline is `{format, id, name, path,
        aspect, text_area}` where path is an SVG path in a box of 100 by 100."""
        deck = _deck(ctx)
        return {
            "library": [shape.to_data() for shape in library],
            "document": [shape.to_data() for _, shape in sorted(deck.shapes.items())],
        }

    @table.method("styles")
    def _styles(ctx):
        """The named looks objects refer to, each as `{id, name, purpose, css}`."""
        return [style.to_data() for style in BUILTIN_STYLES.values()]

    @table.method("add_slide", "base:revision?", write=True)
    def _add_slide(ctx, base):
        """Add an empty slide at the end. Returns its id and the revision."""
        slide = _fresh("s", _deck(ctx).slides)
        return _done(ctx, AddSlide(slide), base, slide=slide)

    @table.method(
        "add_object", 'slide:str kind:str x:int y:int w:int h:int shape:str? text:text="" base:revision?', write=True
    )
    def _add_object(ctx, *, slide, kind, x, y, w, h, shape, text, base):
        """Put a text box (`kind` "text") or a shape (`kind` "shape" with the `shape` id) on a slide. It gets the
        style of its kind. Returns the new object's id and the revision. A circle must keep its proportions."""
        deck = _deck(ctx)
        if kind not in OBJECT_KINDS:
            raise RequestError("bad_request", f"add_object: kind must be one of {', '.join(OBJECT_KINDS)}")
        if kind == "shape" and shape is None:
            raise RequestError("bad_request", "add_object: a shape needs the id of its outline")
        steps: list = []
        if shape is not None and shape not in deck.shapes:
            outline = library.get(shape)
            if outline is None:
                raise RequestError("bad_request", f"add_object: this server has no shape {shape!r}")
            steps.append(DefineShape(outline))
        object_id = _fresh("o", deck.objects)
        steps.append(AddObject(SlideObject(object_id, slide, kind, x, y, w, h, STYLE_OF_KIND[kind], text, shape)))
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add shape")
        return _done(ctx, command, base, object=object_id)

    @table.method("move_object", "id:str x:int y:int base:revision?", write=True)
    def _move_object(ctx, *, id, x, y, base):
        """Move an object so that its top left corner is at (x, y)."""
        return _done(ctx, MoveObject(id, x, y), base)

    @table.method("resize_object", "id:str x:int y:int w:int h:int base:revision?", write=True)
    def _resize_object(ctx, *, id, x, y, w, h, base):
        """Give an object a new frame: top left corner and size (resizing from the left or top moves the corner)."""
        return _done(ctx, ResizeObject(id, x, y, w, h), base)

    @table.method("set_text", "id:str text:text base:revision?", write=True)
    def _set_text(ctx, *, id, text, base):
        """Replace the text of an object."""
        return _done(ctx, SetText(id, text), base)

    @table.method("remove_object", "id:str base:revision?", write=True)
    def _remove_object(ctx, *, id, base):
        """Take an object off its slide. Undo brings it back in the same place of the stacking order."""
        return _done(ctx, RemoveObject(id), base)

    return table


creates_methods = creates_methods_with(ShapeLibrary.load())
