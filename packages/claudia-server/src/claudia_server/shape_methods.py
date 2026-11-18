"""Text boxes and shapes as objects, the same in every app that lets a person put them somewhere (E10.16, D1065).

A text box and a shape are objects of the kernel's object layer (:class:`claudia_core.ObjectModel`) like pictures
are; what differs between apps is only *where* one hangs, and that is the app's :class:`Placement`. So ``shapes`` and
``add_object`` are registered here once, for presentations (a point on a slide) and texts (a character of a
paragraph) alike; sheets do not use them yet. Pictures, containers and charts each come from a request of their
own (``add_image``, ``add_rendering``, a chart in computes), and ``add_object`` says so when asked for one."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from claudia_core import AddObject, Batch, DefineShape, ObjectBody, ObjectModel, paragraph_for
from claudia_creates import ShapeLibrary

from .i18n import msg
from .object_methods import Placement, spec
from .protocol import Context, MethodTable, RequestError
from .thing_names import default_name
from .wire import done, fresh_id

#: The style a new object of each kind starts with: its container's slot (D304). A text box's box is a box style
#: of its own (D310), so a change to it never has to deviate from Body text.
STYLE_OF_KIND = {"text": "plain-box", "shape": "plain-shape"}
#: The style a new object's words start with: its words' slot. A shape's outline and its words are two styles of
#: two kinds (D310).
PARAGRAPH_STYLE_OF_KIND = {"text": "body-text", "shape": "shape-label"}
#: What `add_object` makes; a picture, a container and a chart each come from their own request.
ADDABLE_KINDS = tuple(PARAGRAPH_STYLE_OF_KIND)


def check_addable(kind: str, shape: str | None) -> None:
    """Refuse, saying where to go instead, a kind that `add_object` does not make: a picture, a container and a chart
    each come from a definition of their own."""
    if kind == "image":
        raise RequestError("bad_request", msg("add_object: use add_image to put a picture here"))
    if kind == "rendered":
        raise RequestError("bad_request", msg("add_object: use add_rendering to put a container here"))
    if kind == "diagram":
        raise RequestError("bad_request", msg("add_object: a chart is made in computes, not here"))
    if kind not in ADDABLE_KINDS:
        raise RequestError(
            "bad_request", msg("add_object: kind must be one of {kinds}", kinds=", ".join(ADDABLE_KINDS))
        )
    if kind == "shape" and shape is None:
        raise RequestError("bad_request", msg("add_object: a shape needs the id of its outline"))


def add_shape_methods(
    table: MethodTable,
    *,
    model_of: Callable[[Context], ObjectModel],
    library: ShapeLibrary,
    placement: Placement,
    words_styles: Mapping[str, str] = PARAGRAPH_STYLE_OF_KIND,
) -> None:
    """Register ``shapes`` and ``add_object`` on ``table``: the outlines the server offers and the ones the document
    has taken in, and a text box or a shape put where ``placement`` says. ``words_styles`` is the style the words of
    a new text box (`text`) and a new shape (`shape`) start in, where an app's own body style is not Body text's."""
    say = placement.help

    def shapes(ctx: Context) -> dict:
        model = model_of(ctx)
        return {
            "library": [shape.to_data() for shape in library],
            "document": [shape.to_data() for _, shape in sorted(model.shapes.items())],
        }

    shapes.__doc__ = say(
        "shapes",
        "The outlines: `{library, document}`. `library` is what the server offers for insertion, `document` what "
        "this document has taken in (and what its objects are drawn with). An outline is `{format, id, name, path, "
        "aspect, text_area}` where path is an SVG path in a box of 100 by 100.",
    )
    table.method("shapes")(shapes)

    def add_object(ctx: Context, *, kind, w, h, shape, text, base, **where) -> dict:
        model = model_of(ctx)
        check_addable(kind, shape)
        anchor = placement.anchor(model, None, **where)
        steps: list = []
        if shape is not None and shape not in model.shapes:
            outline = library.get(shape)
            if outline is None:
                raise RequestError("bad_request", msg("add_object: this server has no shape {shape!r}", shape=shape))
            steps.append(DefineShape(outline))
        object_id = fresh_id("o", model.objects)
        words = paragraph_for(object_id, words_styles[kind], text, ctx.user)
        body = ObjectBody(object_id, kind, w, h, STYLE_OF_KIND[kind], words, ref=shape, name=default_name(ctx, kind))
        steps.append(AddObject(body, anchor))
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add shape")
        return done(ctx, command, base, object=object_id)

    add_object.__doc__ = say(
        "add_object",
        'Put a text box (`kind` "text") or a shape (`kind` "shape" with the `shape` id) here. Its words are a '
        "paragraph (E10.17): it starts under the object's own style, and `set_paragraph_style` points it at another. "
        "It gets the style of its kind. Returns the new object's id and the revision. A circle must keep its "
        "proportions.",
    )
    table.method(
        "add_object", spec(placement.new, 'kind:str w:int h:int shape:str? text:text="" base:revision?'), write=True
    )(add_object)


__all__ = ["ADDABLE_KINDS", "PARAGRAPH_STYLE_OF_KIND", "STYLE_OF_KIND", "add_shape_methods", "check_addable"]
