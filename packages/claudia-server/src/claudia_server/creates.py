"""The methods of the presentation app: what a slide view needs to show a slide and to take what people do on it.

``creates_methods`` is ``core_methods`` plus ``slides``, ``slide``, ``shapes``, ``styles``, ``add_slide``,
``set_slide_notes``, ``set_slide_time`` (speaker notes and planned times, D342, D343),
``search_find``, ``search_preview`` and ``search_replace`` (:mod:`claudia_server.creates_search`, E10.19),
``add_object``, ``add_image``, ``move_object``, ``resize_object``, ``set_text``, ``write_words``, ``set_snap`` and
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

from claudia_creates_io import (
    apply_edits_to_odp,
    apply_edits_to_pptx,
    odp_export_losses,
    odp_unwritten_changes,
    pptx_export_losses,
    pptx_unwritten_changes,
    slides_to_odp,
    slides_to_pptx,
)

from claudia_core import (
    AddObject,
    Batch,
    DefineShape,
    ObjectBody,
    PageSetupError,
    SetSnap,
    SetText,
    Toc,
    paragraph_for,
    word_changes,
)
from claudia_creates import (
    AddSlide,
    PrintSetup,
    PrintSetupError,
    SetPrintSetup,
    SetSlideNotes,
    SetSlideTime,
    ShapeLibrary,
    SlideAnchor,
    SlideModel,
)

from .creates_search import add_search_methods
from .i18n import msg
from .object_methods import Placement, add_object_methods
from .office_export import document_info, export_with_original, office_export
from .printing import add_language_methods, people_only
from .protocol import Context, MethodTable, RequestError, core_methods
from .rendered import add_rendering_methods
from .replay import add_replay_methods
from .structure_methods import add_structure_methods
from .styles import add_style_methods
from .thing_names import add_name_methods, default_name
from .wire import current_revision, done, fresh_id

#: The style a new object of each kind starts with: its container's slot (D304). A text box's box is a box style
#: of its own (D310), so a change to it never has to deviate from Body text.
STYLE_OF_KIND = {"text": "plain-box", "shape": "plain-shape"}
#: The style a new object's words start with: its words' slot. A shape's outline and its words are two styles of
#: two kinds (D310).
PARAGRAPH_STYLE_OF_KIND = {"text": "body-text", "shape": "shape-label"}
#: What `add_object` makes; a picture, a container and a chart each come from their own request.
ADDABLE_KINDS = tuple(PARAGRAPH_STYLE_OF_KIND)


def _check_addable(kind: str, shape: str | None) -> None:
    """Refuse, saying where to go instead, a kind that `add_object` does not make: a picture, a container and a chart
    each come from a definition of their own."""
    if kind == "image":
        raise RequestError("bad_request", msg("add_object: use add_image to put a picture on a slide"))
    if kind == "rendered":
        raise RequestError("bad_request", msg("add_object: use add_rendering to put a container on a slide"))
    if kind == "diagram":
        raise RequestError("bad_request", msg("add_object: a chart is made in computes, not on a slide"))
    if kind not in ADDABLE_KINDS:
        raise RequestError(
            "bad_request", msg("add_object: kind must be one of {kinds}", kinds=", ".join(ADDABLE_KINDS))
        )
    if kind == "shape" and shape is None:
        raise RequestError("bad_request", msg("add_object: a shape needs the id of its outline"))


def _deck(ctx: Context) -> SlideModel:
    model = ctx.document.model
    if not isinstance(model, SlideModel):
        raise RequestError("command_error", msg("this document is not a presentation"))
    return model


def _set_text(ctx, *, id, text, base):
    """Replace the text of an object."""
    return done(ctx, SetText(id, text), base)


def _write_words(ctx, *, id, text, base):
    """Write the words of an object as `text`, as a person types them (step G): only what differs from the words it
    has now changes, so the words that stay keep who wrote them, where `set_text` would give them all to whoever
    saved. One step in the history; none when nothing changed. `command_error` for a picture or an agenda."""
    words = _deck(ctx).get_object(id).body.paragraph
    if words is None:
        raise RequestError("command_error", msg("an image carries no text"))
    steps = word_changes(id, words.text, text)
    if not steps:
        return {"revision": current_revision(ctx)}
    return done(ctx, Batch(steps, "Edit text"), base)


def _set_snap(ctx, *, id, snap, base):
    """Hold an object to the grid (`snap` true) or release it (false). The grid is only a helper the view
    draws, never part of the slide, but this choice is: it has its own place in the document's history."""
    return done(ctx, SetSnap(id, snap), base)


def _on_slide(_deck: SlideModel, held: SlideAnchor | None, *, x: int, y: int, slide: str = "") -> dict:
    """Where an object of a presentation is: its top left corner on a slide. A new one names its slide; a moved one
    stays on its own."""
    return SlideAnchor(slide if held is None else held.slide, x, y).to_data()


ON_SLIDE = Placement(
    new="slide:str x:int y:int",
    move="x:int y:int",
    frame="x:int y:int",
    anchor=_on_slide,
    says={
        "add_image": "`x` and `y` are its top left corner.",
        "move_object": "`x` and `y` are its top left corner now.",
        "resize_object": "The top left corner (`x`, `y`) comes with the size, since resizing from the left or top "
        "moves the corner.",
        "rotate_object": "A slide keeps the turned outline of what is on it on the slide, so a turn that would push a "
        "corner off also moves the object just far enough in, in the same step of the history; one that cannot fit at "
        "all is refused.",
    },
)


def _add_object_methods(table: MethodTable) -> None:
    """The methods that change one object, the same in every app (CODE-27), and what only a slide's objects have:
    words of their own and a hold to the grid."""
    add_object_methods(table, model_of=_deck, placement=ON_SLIDE)
    add_rendering_methods(table, model_of=_deck, placement=ON_SLIDE)
    table.method("set_text", "id:str text:text base:revision?", write=True)(_set_text)
    table.method("write_words", "id:str text:text base:revision?", write=True)(_write_words)
    table.method("set_snap", "id:str snap:bool base:revision?", write=True)(_set_snap)


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
        return done(ctx, command, base)


def _add_plan_methods(table: MethodTable) -> None:
    """The speaker notes (D342) and planned times (D343) of the slides: what a talk is prepared with."""

    @table.method("set_slide_notes", "slide:str notes:text base:revision?", write=True)
    def _set_slide_notes(ctx, *, slide, notes, base):
        """Set the speaker notes of a slide (D342), Markdown, shown formatted in the presenter view only; `""` clears
        them. `command_error` for an unknown slide or notes that cannot be kept."""
        return done(ctx, SetSlideNotes(slide, notes), base)

    @table.method("set_slide_time", "slide:str seconds:int? base:revision?", write=True)
    def _set_slide_time(ctx, *, slide, seconds, base):
        """Set the planned time of a slide (D343) in whole seconds, 1 to 86400; `null` clears it. `command_error`
        for an unknown slide or a time that makes no sense."""
        return done(ctx, SetSlideTime(slide, seconds), base)


def _add_shared_methods(table: MethodTable) -> None:
    """What presentations answer the way the other apps do: ``styles``, ``palette``, ``change_style``,
    ``rename_style``, ``check_css`` and ``set_object_style`` (E1.10, D200), the objects (E10.16), the notes and
    planned times (D342, D343), search and replace (E10.19), printing and the language (D917), and lists in text
    boxes, numbered slide titles and numbering schemes (:mod:`claudia_server.structure_methods`, E9.21, E9.22)."""
    add_style_methods(table)
    _add_object_methods(table)
    add_name_methods(table)
    add_replay_methods(table)
    _add_print_methods(table)
    _add_plan_methods(table)
    add_search_methods(table)
    add_structure_methods(table)


def creates_methods_with(library: ShapeLibrary) -> MethodTable:
    """The method table of presentations on a server whose shape library is ``library``."""
    table = core_methods.extended()
    _add_shared_methods(table)

    @table.method("slides")
    def _slides(ctx):
        """The slides in order, each as `{id, name, objects, seconds, has_notes}`: its name (`""` for a slide from
        before names, see `name_unnamed`), how many things are on it, its planned time in seconds (`null` when it has
        none, D343) and whether it has speaker notes (D342, read them with `slide`)."""
        deck = _deck(ctx)
        return [
            {
                "id": slide,
                "objects": len(deck.objects_on(slide)),
                "seconds": deck.times.get(slide),
                "has_notes": slide in deck.notes,
                "name": deck.slide_names.get(slide, ""),
            }
            for slide in deck.slides
        ]

    @table.method("slide", "slide:str")
    def _slide(ctx, slide):
        """One slide as `{revision, slide, objects, notes, seconds}`: its objects, the one in front last, its speaker
        notes in Markdown (`""` if none, D342) and its planned time in seconds (`null` if none, D343). An object is
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
        return {
            "revision": current_revision(ctx),
            "slide": slide,
            "objects": objects,
            "notes": deck.notes_of(slide),
            "seconds": deck.time_of(slide),
        }

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
            return export_with_original(
                ctx,
                format,
                SlideModel,
                lambda original, baseline, current, _: apply_edits_to_pptx(original, baseline, current),
                lambda: office_export(
                    format, slides_to_pptx(deck, rasterise=draw), pptx_export_losses(deck, rasterised=draw is not None)
                ),
                pptx_unwritten_changes,
            )
        info = document_info(ctx.document.log, ctx.document.branch)
        return export_with_original(
            ctx,
            format,
            SlideModel,
            lambda original, baseline, current, found: apply_edits_to_odp(
                original, baseline, current, losses=found, info=info
            ),
            lambda: office_export(
                format,
                slides_to_odp(deck, info=info, rasterise=draw),
                odp_export_losses(deck, rasterised=draw is not None),
            ),
            odp_unwritten_changes,
        )

    @table.method("add_slide", "base:revision?", write=True)
    def _add_slide(ctx, base):
        """Add an empty slide at the end. Returns its id and the revision."""
        slide = fresh_id("s", _deck(ctx).slides)
        return done(ctx, AddSlide(slide, name=default_name(ctx, "slide")), base, slide=slide)

    @table.method(
        "add_object", 'slide:str kind:str x:int y:int w:int h:int shape:str? text:text="" base:revision?', write=True
    )
    def _add_object(ctx, *, slide, kind, x, y, w, h, shape, text, base):
        """Put a text box (`kind` "text") or a shape (`kind` "shape" with the `shape` id) on a slide. Its words
        are a paragraph (E10.17): it starts under the object's own style, and `set_paragraph_style` points it at
        another. It gets the
        style of its kind. Returns the new object's id and the revision. A circle must keep its proportions."""
        deck = _deck(ctx)
        _check_addable(kind, shape)
        steps: list = []
        if shape is not None and shape not in deck.shapes:
            outline = library.get(shape)
            if outline is None:
                raise RequestError("bad_request", msg("add_object: this server has no shape {shape!r}", shape=shape))
            steps.append(DefineShape(outline))
        object_id = fresh_id("o", deck.objects)
        style = STYLE_OF_KIND[kind]
        words = paragraph_for(object_id, PARAGRAPH_STYLE_OF_KIND[kind], text, ctx.user)
        body = ObjectBody(object_id, kind, w, h, style, words, shape=shape, name=default_name(ctx, kind))
        steps.append(AddObject(body, SlideAnchor(slide, x, y).to_data()))
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add shape")
        return done(ctx, command, base, object=object_id)

    @table.method("insert_agenda", "slide:str base:revision?", write=True)
    def _insert_agenda(ctx, *, slide, base):
        """Put an agenda on a slide (E9.31): a text box whose words are the titles of all slides with their slide
        numbers, derived, so it follows every new, retitled or moved slide. Its options are `set_contents`'; it is
        taken away as any object is. One step. Returns the new object's id and the revision."""
        deck = _deck(ctx)
        object_id = fresh_id("o", deck.objects)
        x, y, w, h = AGENDA_BOX
        words = paragraph_for(object_id, PARAGRAPH_STYLE_OF_KIND["text"], "", ctx.user).with_generated(Toc(1, 1))
        body = ObjectBody(object_id, "text", w, h, STYLE_OF_KIND["text"], words, name=default_name(ctx, "text"))
        return done(ctx, AddObject(body, SlideAnchor(slide, x, y).to_data()), base, object=object_id)

    return table


#: Where an agenda goes on its slide, in slide units (the 1600 by 900 stage): below the title, across the slide.
AGENDA_BOX = (160, 250, 1280, 560)

creates_methods = creates_methods_with(ShapeLibrary.load())
