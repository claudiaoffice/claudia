"""Rendered text containers over the wire: the same methods in the apps that place objects (D390, D395).

A container is a definition (the text the person writes, kept as the truth) and an object that shows it. The wire only
ever changes the text; the picture is made by the render service and comes back through the document like any edit.
These tests use a stand-in service: that the real tools render is the business of ``claudia-render``."""

import asyncio
import json

import pytest

from claudia_composes import TextModel
from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore, ResizeObject
from claudia_creates import SlideModel
from claudia_render import CliPlugin, PluginRegistry, Rendered, parse_manifest
from claudia_server.apps import MODEL_METHODS
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError
from claudia_server.rendered import RenderDesk

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")

MANIFEST = {
    "api": 1,
    "type": "boxer",
    "version": "1.0",
    "title": "Boxer",
    "requires": [{"tool": "boxer"}],
    "params": [{"name": "theme", "type": "string", "default": "plain", "choices": ["plain", "dark"]}],
    "cli": {"argv": ["${tool.boxer}", "${input}", "${output}"], "output": "out.svg"},
    "max_source_chars": 40,
    "editor": {"example": "hello", "ai_hint": "One box per line."},
}
GLYPHS = (
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="10">'
    '<defs><symbol id="g"><path d="M0 0L5 5"/></symbol></defs><use xlink:href="#g"/></svg>'
)


class StubService:
    """What `RenderService` is to the desk: plugins and an async ``render``. It draws what it is told to."""

    def __init__(self, svg=GLYPHS):
        self.plugins = PluginRegistry()
        self.plugins.register(CliPlugin(parse_manifest(MANIFEST), "/tmp/unused"))  # noqa: S108
        self.svg = svg
        self.seen = []
        self.during = None  # something that happens while the tool "runs"

    async def render(self, kind, source, params=None):
        self.seen.append((kind, source, dict(params or {})))
        if self.during:
            self.during()
        return Rendered(self.svg, 30.0, 10.0, "boxer 1.0 | boxer 2.5.1 abcd1234")


@pytest.fixture
def service():
    return StubService()


@pytest.fixture
def desk(service):
    return RenderDesk(service)


def call(doc, methods, name, params=None, account=ANN, desk=None):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann"], lock_seconds=30.0, renderings=desk)
    return methods.dispatch(ctx, name, params)


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


@pytest.fixture
def book():
    document = Document(WorkbookModel(), store=MemoryStore())
    document.execute(AddSheet("s1", "Sheet1"), author="ann")
    return document


def put_on_slide(deck, desk, **changes):
    given = {"slide": "s1", "x": 100, "y": 100, "w": 400, "h": 200, "type": "boxer", "source": "hello", **changes}
    return call(deck, creates_methods, "add_rendering", given, desk=desk)


# -- what there is -----------------------------------------------------------------------------------------------------
def test_the_types_are_listed_with_what_an_editor_and_the_ai_need_to_know(deck, desk):
    (one,) = call(deck, creates_methods, "rendering_types", desk=desk)["types"]
    assert one["type"] == "boxer" and one["editor"]["ai_hint"] == "One box per line." and one["max_source_chars"] == 40
    assert "cli" not in json.dumps(one)


def test_a_server_that_renders_nothing_says_so_instead_of_pretending(deck):
    assert call(deck, creates_methods, "rendering_types") == {"types": []}
    with pytest.raises(RequestError) as refused:
        call(
            deck,
            creates_methods,
            "add_rendering",
            {"slide": "s1", "x": 0, "y": 0, "w": 9, "h": 9, "type": "boxer", "source": "x"},
        )
    assert refused.value.code == "unavailable"


# -- adding a container, in the apps that place objects ---------------------------------------------------------------
def test_a_container_on_a_slide_is_its_text_and_an_object_and_undo_takes_both_away(deck, desk):
    added = put_on_slide(deck, desk, alt="Flow of orders")
    model = deck.model
    assert model.get_object(added["object"]).body.rendered == added["rendering"]
    assert model.renderings[added["rendering"]].source == "hello"
    assert model.get_object(added["object"]).body.description == "Flow of orders"
    assert call(deck, creates_methods, "renderings", desk=desk)[0]["source"] == "hello"
    deck.undo("ann")
    assert model.objects == {} and model.renderings == {}


def test_a_container_on_a_sheet_hangs_on_a_cell(book, desk):
    given = {"sheet": "s1", "row": 2, "col": 3, "w": 300, "h": 160, "type": "boxer", "source": "hi"}
    added = call(book, computes_methods, "add_rendering", given, desk=desk)
    anchor = book.model.get_object(added["object"]).anchor
    assert (anchor.row, anchor.col) == (2, 3) and book.model.renderings[added["rendering"]].type == "boxer"


def test_the_text_app_can_read_containers_and_the_types(desk):
    text = Document(TextModel(), store=MemoryStore())
    assert call(text, composes_methods, "renderings", desk=desk) == []
    assert call(text, composes_methods, "rendering_types", desk=desk)["types"][0]["type"] == "boxer"


# -- the text app places them too: a container hangs from a character of a paragraph (D560) ----------------------------
@pytest.fixture
def text():
    document = Document(TextModel(), store=MemoryStore())
    call(
        document,
        composes_methods,
        "replace_text",
        {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "Hello world"},
    )
    return document


def put_in_text(text, desk, **changes):
    given = {"block": "b1", "offset": 5, "w": 400, "h": 200, "type": "boxer", "source": "hello", **changes}
    return call(text, composes_methods, "add_rendering", given, desk=desk)


def test_a_container_in_a_text_hangs_from_a_character_of_its_paragraph(text, desk):
    added = put_in_text(text, desk)
    anchor = text.model.get_object(added["object"]).anchor
    assert (anchor.block, anchor.offset) == ("b1", 5)
    assert text.model.renderings[added["rendering"]].source == "hello"
    text.undo("ann")
    assert text.model.objects == {} and text.model.renderings == {}


def test_a_container_cannot_hang_from_nowhere(text, desk):
    for changes in ({"block": "nope"}, {"offset": 99}, {"offset": -1}):
        with pytest.raises(RequestError):
            put_in_text(text, desk, **changes)
    assert text.model.objects == {}


def test_a_container_in_a_text_is_moved_sized_and_taken_away(text, desk):
    object_id = put_in_text(text, desk)["object"]
    call(text, composes_methods, "move_object", {"id": object_id, "block": "b1", "offset": 2})
    assert text.model.get_object(object_id).anchor.offset == 2
    call(text, composes_methods, "resize_object", {"id": object_id, "w": 320, "h": 120})
    body = text.model.get_object(object_id).body
    assert (body.w, body.h) == (320, 120)
    call(text, composes_methods, "remove_object", {"id": object_id})
    assert text.model.objects == {}
    text.undo("ann")
    assert object_id in text.model.objects


def test_a_container_is_not_moved_out_of_the_text(text, desk):
    object_id = put_in_text(text, desk)["object"]
    with pytest.raises(RequestError):
        call(text, composes_methods, "move_object", {"id": object_id, "block": "b1", "offset": 99})
    with pytest.raises(RequestError):
        call(text, composes_methods, "move_object", {"id": object_id, "block": "nope", "offset": 0})


def test_in_the_text_the_assistant_as_deployed_does_not_place_containers(text, desk):
    with pytest.raises(RequestError) as refused:
        call(
            text,
            composes_methods,
            "add_rendering",
            {"block": "b1", "offset": 0, "w": 9, "h": 9, "type": "boxer", "source": "x"},
            account=Account.assistant(MODEL_METHODS["composes"]),
            desk=desk,
        )
    assert refused.value.code == "forbidden"


def test_an_unknown_type_a_wrong_setting_and_too_long_a_text_are_refused_and_nothing_changes(deck, desk):
    for changes, words in (
        ({"type": "graphviz"}, "boxer"),
        ({"params": {"theme": "neon"}}, "theme"),
        ({"params": {"colour": "red"}}, "no such setting"),
        ({"source": "x" * 41}, "40"),
    ):
        with pytest.raises(RequestError, match=words):
            put_on_slide(deck, desk, **changes)
    assert deck.model.objects == {} and deck.model.renderings == {}


def test_somebody_who_may_only_look_cannot_add_one(deck, desk):
    with pytest.raises(RequestError) as refused:
        call(
            deck,
            creates_methods,
            "add_rendering",
            {"slide": "s1", "x": 0, "y": 0, "w": 9, "h": 9, "type": "boxer", "source": "x"},
            account=VERA,
            desk=desk,
        )
    assert refused.value.code == "forbidden"


# -- changing the text ------------------------------------------------------------------------------------------------
def test_the_text_is_changed_by_the_id_of_the_container_and_undo_brings_the_old_one_back(deck, desk):
    added = put_on_slide(deck, desk)
    call(
        deck,
        creates_methods,
        "set_rendering_source",
        {"id": added["rendering"], "source": "new text", "params": {"theme": "dark"}},
        desk=desk,
    )
    now = deck.model.renderings[added["rendering"]]
    assert (now.source, dict(now.params)) == ("new text", {"theme": "dark"})
    deck.undo("ann")
    assert deck.model.renderings[added["rendering"]].source == "hello"


def test_a_text_for_a_container_nobody_has_is_refused(deck, desk):
    with pytest.raises(RequestError, match="nothing"):
        call(deck, creates_methods, "set_rendering_source", {"id": "r404", "source": "x"}, desk=desk)


# -- the picture comes back through the document ----------------------------------------------------------------------
def render(desk, document, rendering_id):
    return asyncio.run(desk.render_into(document, "ann", rendering_id))


def test_a_picture_is_taken_into_the_document_with_what_made_it_and_a_description_for_whoever_cannot_see_it(deck, desk):
    added = put_on_slide(deck, desk)
    done = render(desk, deck, added["rendering"])
    definition = deck.model.renderings[added["rendering"]]
    assert done is not None and definition.image in deck.model.images and definition.renderer.startswith("boxer 1.0")
    assert deck.model.images[definition.image].format == "svg" and b"<use" in deck.model.images[definition.image].data
    assert deck.model.get_object(added["object"]).body.description.startswith("boxer: hello")
    deck.undo("ann")
    assert deck.model.renderings[added["rendering"]].image is None and deck.model.images == {}


def test_a_description_a_person_wrote_is_not_replaced(deck, desk):
    added = put_on_slide(deck, desk, alt="Flow of orders")
    render(desk, deck, added["rendering"])
    assert deck.model.get_object(added["object"]).body.description == "Flow of orders"


def test_a_later_picture_replaces_the_earlier_one_and_the_old_one_does_not_pile_up(deck, desk, service):
    added = put_on_slide(deck, desk)
    render(desk, deck, added["rendering"])
    first = deck.model.renderings[added["rendering"]].image
    service.svg = GLYPHS.replace('width="30"', 'width="31"')
    render(desk, deck, added["rendering"])
    second = deck.model.renderings[added["rendering"]].image
    assert second != first and set(deck.model.images) == {second}
    deck.undo("ann")
    assert deck.model.renderings[added["rendering"]].image == first and set(deck.model.images) == {first}


def test_the_same_picture_again_changes_nothing(deck, desk):
    added = put_on_slide(deck, desk)
    render(desk, deck, added["rendering"])
    before = deck.revision
    render(desk, deck, added["rendering"])
    assert deck.revision == before


def test_a_picture_for_a_text_that_has_changed_meanwhile_is_not_taken(deck, desk, service):
    added = put_on_slide(deck, desk)
    service.during = lambda: call(
        deck, creates_methods, "set_rendering_source", {"id": added["rendering"], "source": "changed"}, desk=desk
    )
    assert render(desk, deck, added["rendering"]) is None
    assert deck.model.renderings[added["rendering"]].image is None


# -- a file made of the document --------------------------------------------------------------------------------------
def test_a_container_goes_into_an_office_file_as_the_picture_made_from_its_text(deck, desk):
    added = put_on_slide(deck, desk, alt="Flow of orders")
    pending = call(deck, creates_methods, "export_office", {"format": "pptx"}, desk=desk)
    assert pending["losses"] == [{"kind": "rendering-pending", "detail": "", "count": 1}]
    render(desk, deck, added["rendering"])
    assert call(deck, creates_methods, "export_office", {"format": "odp"}, desk=desk)["losses"] == [
        {"kind": "svg-picture", "detail": "", "count": 1}
    ]
    assert call(deck, creates_methods, "export_office", {"format": "pptx"}, desk=desk)["losses"] == [
        {"kind": "svg-fallback", "detail": "", "count": 1}
    ]


def test_with_a_rasteriser_the_files_hold_a_picture_every_program_draws_and_lose_nothing(deck, service):
    from io import BytesIO

    from PIL import Image

    made = BytesIO()
    Image.new("RGBA", (30, 10), (200, 30, 30, 255)).save(made, "PNG")
    desk = RenderDesk(service, rasteriser=lambda svg, w, h: made.getvalue())
    added = put_on_slide(deck, desk)
    render(desk, deck, added["rendering"])
    for fmt in ("odp", "pptx"):
        assert call(deck, creates_methods, "export_office", {"format": fmt}, desk=desk)["losses"] == []


# -- the frame follows the picture ------------------------------------------------------------------------------------
def test_the_frame_keeps_its_width_and_takes_the_proportions_of_the_picture(deck, desk):
    added = put_on_slide(deck, desk, w=300, h=200)
    render(desk, deck, added["rendering"])
    body = deck.model.get_object(added["object"]).body
    assert (body.w, body.h) == (300, 100), "the picture is three times as wide as it is high"
    deck.undo("ann")
    assert deck.model.get_object(added["object"]).body.h == 200


# -- a new container is no bigger than its picture (the owner, 2026-11-19: the smaller of 420 × 240 and the picture)
def test_a_container_added_to_fit_is_shown_at_its_pictures_own_size_if_that_is_smaller(deck, desk):
    added = put_on_slide(deck, desk, w=420, h=240, fit=True)
    render(desk, deck, added["rendering"])
    body = deck.model.get_object(added["object"]).body
    # D1332: and at least as tall as the body text (40 on a slide), with its proportions; it used to be 30 × 20
    assert (body.w, body.h) == (120, 40), "the picture is 30 × 10, raised to the body text's 40"


def test_a_container_added_to_fit_goes_into_its_frame_if_the_picture_is_larger(deck, desk):
    big = GLYPHS.replace('width="30" height="10"', 'width="1200" height="400"')
    desk.service.svg = big
    added = put_on_slide(deck, desk, w=420, h=240, fit=True)
    render(desk, deck, added["rendering"])
    body = deck.model.get_object(added["object"]).body
    assert (body.w, body.h) == (420, 140), "three times as wide as high, as wide as the frame"


def test_a_container_added_without_fit_keeps_the_frame_it_was_given(deck, desk):
    added = put_on_slide(deck, desk, w=300, h=200)
    render(desk, deck, added["rendering"])
    assert deck.model.get_object(added["object"]).body.w == 300


def test_only_the_first_picture_is_capped(deck, desk):
    added = put_on_slide(deck, desk, w=420, h=240, fit=True)
    render(desk, deck, added["rendering"])
    deck.execute(
        ResizeObject(added["object"], deck.model.get_object(added["object"]).anchor.to_data(), 300, 100), author="ann"
    )
    call(deck, creates_methods, "set_rendering_source", {"id": added["rendering"], "source": "again"}, desk=desk)
    render(desk, deck, added["rendering"])
    assert deck.model.get_object(added["object"]).body.w == 300, "a second picture keeps the width the person gave it"
