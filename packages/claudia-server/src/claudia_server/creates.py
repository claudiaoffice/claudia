"""The methods of the presentation app: what a slide view needs to show a slide and to take what people do on it.

``creates_methods`` is ``core_methods`` plus ``slides``, ``slide``, ``shapes``, ``styles``, ``add_slide``,
``add_object``, ``add_image``, ``move_object``, ``resize_object``, ``set_text``, ``set_snap`` and
``remove_object``. Positions and sizes are whole units of the slide space (1600 by 900). A shape is chosen by its
id from the server's shape library;
the first time a document uses it, its outline is copied into the document, in the same step of the history as the
object, so a document never depends on the library of the server it is opened on. An image is decoded from the
bytes the client sends (``add_image``); the first time a document sees that exact picture, the decoded asset is
copied into the document the same way. Importing from the clipboard or by drag-and-drop is not implemented yet
(``add_image`` only takes a file's bytes, as a disk import does). Every write may carry the ``base`` revision of the
client's view, as ``apply`` does.

``creates_methods_with(library)`` makes the table for a server whose library holds more than the built-in shapes.
"""

from __future__ import annotations

import secrets

from claudia_creates_io import odp_export_losses, pptx_export_losses, slides_to_odp, slides_to_pptx

from claudia_core import (
    OBJECT_KINDS,
    AddObject,
    Batch,
    DefineImage,
    DefineShape,
    DescribeObject,
    ImageImport,
    MoveObject,
    ObjectBody,
    PageSetupError,
    RemoveObject,
    ResizeObject,
    RotateObject,
    SetSnap,
    SetText,
    decode_image,
    paragraph_for,
)
from claudia_core.clock import utc_now
from claudia_creates import AddSlide, PrintSetup, PrintSetupError, SetPrintSetup, ShapeLibrary, SlideAnchor, SlideModel

from .i18n import msg
from .images import image_bytes, picture_words
from .office_export import document_info, office_export
from .printing import add_language_methods, people_only
from .protocol import Context, MethodTable, RequestError, core_methods
from .rendered import add_rendering_methods
from .styles import add_style_methods

#: The style a new object of each kind starts with: its container's slot (D304). A text box's box is a box style
#: of its own (D310), so a change to it never has to deviate from Body text.
STYLE_OF_KIND = {"text": "plain-box", "shape": "plain-shape", "image": "plain-image"}
#: The style a new object's words start with: its words' slot. A shape's outline and its words are two styles of
#: two kinds (D310).
PARAGRAPH_STYLE_OF_KIND = {"text": "body-text", "shape": "shape-label"}


def _deck(ctx: Context) -> SlideModel:
    model = ctx.document.model
    if not isinstance(model, SlideModel):
        raise RequestError("command_error", msg("this document is not a presentation"))
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


def _add_image(ctx, *, slide, x, y, w, h, data, alt, source_name, source_path, decorative, base):
    """Import a picture from disk and put it on a slide: `data` is the file's bytes, base64. `alt` is a short,
    required description of what it shows — unless the picture is only `decorative` (a flourish, a divider),
    when it has none and `alt` is empty. `source_name` is the file name as the client has it; `source_path`
    is its full path if the client could supply one (a plain web browser cannot, for its own security — send
    `null`). Clipboard and drag-and-drop imports are not implemented yet; this is the "browse a file" path.
    Returns the new object's id and the revision. The image keeps its own proportions.

    Module-level, not nested in `creates_methods_with`, because it needs no shape library: only `add_object`
    and `shapes` read from one."""
    deck = _deck(ctx)
    words = picture_words(alt, bool(decorative))
    asset = decode_image(data)
    steps: list = [] if asset.id in deck.images else [DefineImage(asset)]
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
    object_id = _fresh("o", deck.objects)
    body = ObjectBody(
        object_id, "image", w, h, STYLE_OF_KIND["image"], image=asset.id, imported=imported, decorative=bool(decorative)
    )
    steps.append(AddObject(body, SlideAnchor(slide, x, y).to_data()))
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add image")
    return _done(ctx, command, base, object=object_id)


def _move_object(ctx, *, id, x, y, base):
    """Move an object so that its top left corner is at (x, y)."""
    slide = _deck(ctx).get_object(id).anchor.slide
    return _done(ctx, MoveObject(id, SlideAnchor(slide, x, y).to_data()), base)


def _resize_object(ctx, *, id, x, y, w, h, base):
    """Give an object a new frame: top left corner and size (resizing from the left or top moves the corner)."""
    slide = _deck(ctx).get_object(id).anchor.slide
    return _done(ctx, ResizeObject(id, SlideAnchor(slide, x, y).to_data(), w, h), base)


def _rotate_object(ctx, *, id, rotation, base):
    """Turn an object to `rotation` whole degrees clockwise (0 to 359); its frame stays."""
    return _done(ctx, RotateObject(id, rotation), base)


def _set_text(ctx, *, id, text, base):
    """Replace the text of an object."""
    return _done(ctx, SetText(id, text), base)


def _set_snap(ctx, *, id, snap, base):
    """Hold an object to the grid (`snap` true) or release it (false). The grid is only a helper the view
    draws, never part of the slide, but this choice is: it has its own place in the document's history."""
    return _done(ctx, SetSnap(id, snap), base)


def _describe_object(ctx, *, id, description, decorative, base):
    """Say what an object is to someone who cannot see it (`description`, a short sentence), or that it is only
    decoration (`decorative` true, and then no description). A picture needs one or the other."""
    if _deck(ctx).get_object(id).body.kind == "image":
        picture_words(description, bool(decorative))
    return _done(ctx, DescribeObject(id, description, bool(decorative)), base)


def _remove_object(ctx, *, id, base):
    """Take an object off its slide. Undo brings it back in the same place of the stacking order."""
    return _done(ctx, RemoveObject(id), base)


def _add_object_methods(table: MethodTable) -> None:
    """The methods that change one object: import a picture, place it, size it, turn it, word it, style its
    words, hold it to the grid, take it away. Split out of the table builder below only because it had grown
    past the statement limit — they belong together."""
    table.kind("image")(image_bytes)
    table.method(
        "add_image",
        "slide:str x:int y:int w:int h:int data:image alt:str source_name:str source_path:str? decorative:bool? "
        "base:revision?",
        write=True,
    )(_add_image)
    table.method("move_object", "id:str x:int y:int base:revision?", write=True)(_move_object)
    table.method("resize_object", "id:str x:int y:int w:int h:int base:revision?", write=True)(_resize_object)
    table.method("rotate_object", "id:str rotation:int base:revision?", write=True)(_rotate_object)
    table.method("set_text", "id:str text:text base:revision?", write=True)(_set_text)
    table.method("set_snap", "id:str snap:bool base:revision?", write=True)(_set_snap)
    table.method("describe_object", "id:str description:text decorative:bool? base:revision?", write=True)(
        _describe_object
    )
    table.method("remove_object", "id:str base:revision?", write=True)(_remove_object)
    add_rendering_methods(
        table,
        model_of=_deck,
        anchor=(
            "slide:str x:int y:int",
            lambda slide, x, y: SlideAnchor(slide, x, y).to_data(),
            lambda model, **where: None,
        ),
    )


def _add_print_methods(table: MethodTable) -> None:
    """How the presentation is printed (D917), and its language (the kernel's, the same methods as composes')."""
    add_language_methods(table)

    @table.method("print_setup")
    def _print_setup(ctx):
        """How the presentation is printed (D917): `{layout, page}`, `layout` one of `slides`, `handouts-2`,
        `handouts-3`, `handouts-4`, `handouts-6`, `handouts-9`, and `page` as composes' `page` (paper, width,
        height, orientation, margins, page_numbers; lengths in mpt)."""
        return _deck(ctx).print_setup.to_data()

    @table.method("set_print_setup", "setup:dict base:revision?", write=True)
    def _set_print_setup(ctx, *, setup, base):
        """Print the presentation another way (`setup` as `print_setup` returns it). One step for everybody, in
        the history. `command_error` names what is wrong with a setup that cannot be used."""
        people_only(ctx)
        try:
            command = SetPrintSetup(PrintSetup.from_data(setup))
        except (PrintSetupError, PageSetupError) as exc:
            raise RequestError("command_error", str(exc)) from None
        return _done(ctx, command, base)


def _add_shared_methods(table: MethodTable) -> None:
    """What presentations answer the way the other apps do: ``styles``, ``palette``, ``change_style``,
    ``rename_style``, ``check_css`` and ``set_object_style`` (E1.10, D200), the objects (E10.16), and printing and
    the language (D917)."""
    add_style_methods(table)
    _add_object_methods(table)
    _add_print_methods(table)


def creates_methods_with(library: ShapeLibrary) -> MethodTable:
    """The method table of presentations on a server whose shape library is ``library``."""
    table = core_methods.extended()
    _add_shared_methods(table)

    @table.method("slides")
    def _slides(ctx):
        """The slides in order, each as `{id, objects}` where objects is how many things are on it."""
        deck = _deck(ctx)
        return [{"id": slide, "objects": len(deck.objects_on(slide))} for slide in deck.slides]

    @table.method("slide", "slide:str")
    def _slide(ctx, slide):
        """One slide as `{revision, slide, objects}`: its objects, the one in front last. An object is
        `{id, kind, w, h, style, text, shape, image, imported, rotation, snap, anchor}` — the same shape in all
        three apps except for `anchor`, which here is `{kind: "slide", container: <slide>, x, y}` (E10.16).
        `imported`'s `source_path` is only sent to the person who imported that image (everyone else sees `null`
        there, not the path). `snap` is whether the object holds to the grid, a helper the view draws and is free
        to show or hide on its own — `snap` is unaffected by that and is the document's own state, set with
        `set_snap`."""
        deck = _deck(ctx)
        if slide not in deck.slides:
            raise RequestError("command_error", msg("unknown slide {slide!r}", slide=slide))
        objects = [obj.to_data_for(ctx.user) for obj in deck.objects_on(slide)]
        return {"revision": _rev(ctx), "slide": slide, "objects": objects}

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

    @table.method("images")
    def _images(ctx):
        """The decoded image assets this document has taken in (and what its image objects are drawn with), each
        as `{id, format, width, height, animated, data, first_frame}` (`data`/`first_frame` are base64). There is
        no library to pick from: an image always comes in through `add_image`."""
        deck = _deck(ctx)
        return [image.to_data() for _, image in sorted(deck.images.items())]

    @table.method("export_office", "format:str")
    def _export_office(ctx, *, format):
        """The document's current content as bytes of a PowerPoint file (`format` `"pptx"`) or an OpenDocument
        presentation (`"odp"`), wrapped for the wire as `{format, content_type, data}` (`data` base64); an odp's
        answer also has `losses` (a pptx's too), what the file could not hold, as `{kind, detail, count}` codes. No
        tracked changes, no history, no chat -- just the deck as it stands now (D212); an odp says in its metadata
        when the deck was made and last changed, and by whom, read from the log (D411)."""
        if format not in ("pptx", "odp"):
            raise RequestError("bad_request", msg('export_office: format must be "pptx" or "odp"'))
        deck = _deck(ctx)
        draw = None if ctx.renderings is None else ctx.renderings.rasteriser
        if format == "pptx":
            return office_export(
                format, slides_to_pptx(deck, rasterise=draw), pptx_export_losses(deck, rasterised=draw is not None)
            )
        info = document_info(ctx.document.log, ctx.document.branch)
        return office_export(
            format, slides_to_odp(deck, info=info, rasterise=draw), odp_export_losses(deck, rasterised=draw is not None)
        )

    @table.method("add_slide", "base:revision?", write=True)
    def _add_slide(ctx, base):
        """Add an empty slide at the end. Returns its id and the revision."""
        slide = _fresh("s", _deck(ctx).slides)
        return _done(ctx, AddSlide(slide), base, slide=slide)

    @table.method(
        "add_object", 'slide:str kind:str x:int y:int w:int h:int shape:str? text:text="" base:revision?', write=True
    )
    def _add_object(ctx, *, slide, kind, x, y, w, h, shape, text, base):
        """Put a text box (`kind` "text") or a shape (`kind` "shape" with the `shape` id) on a slide. Its words
        are a paragraph (E10.17): it starts under the object's own style, and `set_paragraph_style` points it at
        another. It gets the
        style of its kind. Returns the new object's id and the revision. A circle must keep its proportions."""
        deck = _deck(ctx)
        if kind not in OBJECT_KINDS:
            raise RequestError(
                "bad_request", msg("add_object: kind must be one of {kinds}", kinds=", ".join(OBJECT_KINDS))
            )
        if kind == "shape" and shape is None:
            raise RequestError("bad_request", msg("add_object: a shape needs the id of its outline"))
        if kind == "image":
            raise RequestError("bad_request", msg("add_object: use add_image to put a picture on a slide"))
        steps: list = []
        if shape is not None and shape not in deck.shapes:
            outline = library.get(shape)
            if outline is None:
                raise RequestError("bad_request", msg("add_object: this server has no shape {shape!r}", shape=shape))
            steps.append(DefineShape(outline))
        object_id = _fresh("o", deck.objects)
        style = STYLE_OF_KIND[kind]
        words = paragraph_for(object_id, PARAGRAPH_STYLE_OF_KIND[kind], text, ctx.user)
        body = ObjectBody(object_id, kind, w, h, style, words, shape=shape)
        steps.append(AddObject(body, SlideAnchor(slide, x, y).to_data()))
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add shape")
        return _done(ctx, command, base, object=object_id)

    return table


creates_methods = creates_methods_with(ShapeLibrary.load())
