"""The methods that change one object, the same in every app that holds objects (CODE-27, D177).

The kernel's object layer is one for all apps (:class:`claudia_core.ObjectModel`): place an object, move it, size it,
turn it, describe it, take it away. These are its wire methods, registered once. What differs is only *where* an
object is: a cell of a sheet, a point on a slide, a character of a text. An app says that with a :class:`Placement`,
and :func:`add_object_methods` (and :func:`claudia_server.rendered.add_rendering_methods`) build the rest from it.

What stays with an app is what is really its own: creates' shapes and text boxes (``add_object``, ``set_text``,
``set_snap``), computes' charts, composes' paragraphs. A rule that differs by app, such as a turned object staying
on its slide (D1022), is the kernel's, in the model's own ``turn_command``."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from claudia_core import (
    AddObject,
    Batch,
    DefineAsset,
    DescribeObject,
    ImageImport,
    MoveObject,
    ObjectBody,
    ObjectModel,
    RemoveObject,
    ResizeObject,
    decode_image,
    new_object_size,
)
from claudia_core.asset_store import IMAGE
from claudia_core.clock import utc_now

from .images import image_bytes, picture_words
from .protocol import Context, MethodTable
from .thing_names import default_name
from .wire import done, fresh_id

IMAGE_STYLE = "plain-image"
PICTURE = "w:int h:int data:image alt:str source_name:str source_path:str? decorative:bool? fit:bool?"


@dataclass(frozen=True)
class Placement:
    """How one app says where an object is: its words on the wire and how they become an anchor.

    ``new`` are the words that place a new object (``"sheet:str row:int col:int"``), ``move`` those of
    ``move_object`` besides the id, ``frame`` those of ``resize_object`` besides the id and the size (``""``: a new
    size leaves the anchor as it is). ``anchor(model, held, **words)`` makes the anchor's plain data from them;
    ``held`` is the object's anchor today, ``None`` for a new object, so an app can keep what the words leave out (the
    sheet, the slide, the offset from a character). It raises :class:`~claudia_server.protocol.RequestError` for a
    place that is not there. ``says`` adds to a method's help, per method, what that app's words mean."""

    new: str
    move: str
    frame: str
    anchor: Callable[..., dict]
    says: Mapping[str, str] = field(default_factory=dict)

    def help(self, method: str, text: str) -> str:
        """``text`` with this app's own words about ``method`` after it."""
        return " ".join(part for part in (text, self.says.get(method, "")) if part)


def spec(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def _documented[F: Callable](fn: F, doc: str) -> F:
    fn.__doc__ = doc
    return fn


def add_object_methods(
    table: MethodTable,
    *,
    model_of: Callable[[Context], ObjectModel],
    placement: Placement,
) -> None:
    """Register ``images``, ``add_image``, ``describe_object``, ``move_object``, ``resize_object``, ``rotate_object``
    and ``remove_object`` on ``table``, and the ``image`` parameter kind they take."""
    table.kind("image")(image_bytes)
    say = placement.help

    def images(ctx: Context) -> list[dict]:
        return model_of(ctx).images.to_data()

    table.method("images")(
        _documented(
            images,
            say(
                "images",
                "The decoded image assets this document has taken in (and what its image objects are drawn with), "
                "each as `{id, format, width, height, animated, data, first_frame}` (`data`/`first_frame` are "
                "base64). There is no library to pick from: an image always comes in through `add_image`.",
            ),
        )
    )

    def add_image(
        ctx: Context, *, w, h, data, alt, source_name, source_path, decorative, base, fit=None, **where
    ) -> dict:
        model = model_of(ctx)
        anchor = placement.anchor(model, None, **where)
        words = picture_words(alt, bool(decorative))
        asset = decode_image(data)
        if fit:  # a new picture from a file: within w × h, at least as tall as the body text, in its room (D1332)
            w, h = new_object_size(
                w,
                h,
                asset.width,
                asset.height,
                least=model.least_new_size(),
                room=model.room_for_new_object(model.anchor_from_data(anchor)),
                smallest=model.min_object_size,
            )
        steps: list = [] if asset.id in model.images else [DefineAsset(IMAGE.name, asset.to_data())]
        imported = ImageImport.from_data(
            {
                "asset": asset.id,
                "alt": words,
                "imported_by": ctx.user,
                "imported_at": utc_now(),
                "source": "disk",
                "source_name": source_name,
                "source_path": source_path,
            }
        )
        object_id = fresh_id("o", model.objects)
        body = ObjectBody(
            object_id,
            "image",
            w,
            h,
            IMAGE_STYLE,
            ref=asset.id,
            imported=imported,
            decorative=bool(decorative),
            name=default_name(ctx, "image"),
        )
        steps.append(AddObject(body, anchor))
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add image")
        return done(ctx, command, base, object=object_id)

    table.method("add_image", spec(placement.new, PICTURE, "base:revision?"), write=True)(
        _documented(
            add_image,
            say(
                "add_image",
                "Import a picture from disk and place it: `data` is the file's bytes, base64. `alt` is a "
                "short, required description of what it shows — unless the picture is only `decorative` (a "
                "flourish, a divider), when it has none and `alt` is empty. `source_name` is the file name as the "
                "client has it; `source_path` is its full path if the client could supply one (a plain web browser "
                "cannot, for its own security — send `null`). Returns the new object's id and the revision. The "
                "image keeps its own proportions. With `fit`, `w` and `h` are only the most it may take: it is "
                "shown at its own size within them, but at least as tall as the body text's letters and no wider "
                "than the room it has, with its proportions (D1332); without, it is shown at `w` × `h`.",
            ),
        )
    )

    def describe_object(ctx: Context, *, id, description, decorative, base) -> dict:  # noqa: A002 - the wire name
        if model_of(ctx).get_object(id).body.kind == "image":
            picture_words(description, bool(decorative))
        return done(ctx, DescribeObject(id, description, bool(decorative)), base)

    table.method("describe_object", "id:str description:text decorative:bool? base:revision?", write=True)(
        _documented(
            describe_object,
            say(
                "describe_object",
                "Say what an object is to someone who cannot see it (`description`, a short sentence), or that it is "
                "only decoration (`decorative` true, and then no description). A picture needs one or the other.",
            ),
        )
    )

    def move_object(ctx: Context, *, id, base, **where) -> dict:  # noqa: A002
        model = model_of(ctx)
        anchor = placement.anchor(model, model.get_object(id).anchor, **where)
        return done(ctx, MoveObject(id, anchor), base)

    table.method("move_object", spec("id:str", placement.move, "base:revision?"), write=True)(
        _documented(move_object, say("move_object", "Move an object; its size stays."))
    )

    def resize_object(ctx: Context, *, id, w, h, base, **frame) -> dict:  # noqa: A002
        model = model_of(ctx)
        held = model.get_object(id).anchor
        anchor = placement.anchor(model, held, **frame) if placement.frame else held.to_data()
        return done(ctx, ResizeObject(id, anchor, w, h), base)

    table.method("resize_object", spec("id:str", placement.frame, "w:int h:int base:revision?"), write=True)(
        _documented(
            resize_object,
            say(
                "resize_object",
                "Give an object a new size. An image keeps its own proportions, so `w` and `h` must match them.",
            ),
        )
    )

    def rotate_object(ctx: Context, *, id, rotation, base) -> dict:  # noqa: A002
        return done(ctx, model_of(ctx).turn_command(id, rotation), base)

    table.method("rotate_object", "id:str rotation:int base:revision?", write=True)(
        _documented(
            rotate_object,
            say(
                "rotate_object",
                "Turn an object about its centre to `rotation` whole degrees clockwise; any whole number does (-20 is "
                "340). A chart and a table do not turn.",
            ),
        )
    )

    def remove_object(ctx: Context, *, id, base) -> dict:  # noqa: A002
        return done(ctx, RemoveObject(id), base)

    table.method("remove_object", "id:str base:revision?", write=True)(
        _documented(
            remove_object,
            say(
                "remove_object",
                "Take an object away. Undo brings it back where it was, in the same place of the stacking order.",
            ),
        )
    )


__all__ = ["Placement", "add_object_methods", "spec"]
