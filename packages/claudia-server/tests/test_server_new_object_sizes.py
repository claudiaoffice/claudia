"""How large a new picture or container is, in all three apps (D1229, D1332, D1333; checks the ``@unit`` scenarios of
``claudiaoffice-log/specs/objects/new-object-sizes.feature``).

The models say how tall their body text is and how much room a new object has; the server sizes the first picture of
a container added with ``fit`` and a picture from a file added with ``fit`` by those. The pictures here are made up:
that a real XeLaTeX draws ``E = mc^2`` 43 by 12 is in the feature file's comment.
"""

import asyncio
import base64
import io

import pytest
from PIL import Image

from claudia_composes import TextModel
from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore, ResizeObject
from claudia_creates import SlideModel
from claudia_render import CliPlugin, PluginRegistry, Rendered, parse_manifest
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.containers import RenderDesk
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits

ANN = Account("ann", "owner")
MANIFEST = {
    "api": 1,
    "type": "boxer",
    "version": "1.0",
    "title": "Boxer",
    "requires": [{"tool": "boxer"}],
    "params": [],
    "cli": {"argv": ["${tool.boxer}", "${input}", "${output}"], "output": "out.svg"},
    "max_source_chars": 40,
    "editor": {"example": "hello"},
}


class Drawn:
    """A render service that draws a picture of the size it is told."""

    def __init__(self, w: int, h: int):
        self.plugins = PluginRegistry()
        self.plugins.register(CliPlugin(parse_manifest(MANIFEST), "/tmp/unused"))  # noqa: S108
        self.size = (w, h)

    async def render(self, kind, source, params=None):  # noqa: ARG002
        w, h = self.size
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="{w}" height="{h}"/></svg>'
        return Rendered(svg, float(w), float(h), f"boxer 1.0 {source}")


def call(doc, methods, name, params, desk=None):
    ctx = Context(doc, ANN, Limits(), users=lambda: ["ann"], lock_seconds=30.0, renderings=desk)
    return methods.dispatch(ctx, name, params)


def text_doc():
    d = Document(TextModel(), store=MemoryStore())
    call(
        d,
        composes_methods,
        "replace_text",
        {"paragraph": "b1", "start": 0, "end_paragraph": "b1", "end": 0, "text": "Hi"},
    )
    return d


def sheet_doc():
    d = Document(WorkbookModel(), store=MemoryStore())
    d.execute(AddSheet("s1", "Sheet1"), author="ann")
    return d


def deck_doc():
    return Document(SlideModel.empty(), store=MemoryStore())


APPS = {
    "composes": (text_doc, composes_methods, {"paragraph": "b1", "offset": 2}),
    "computes": (sheet_doc, computes_methods, {"sheet": "s1", "row": 1, "col": 1}),
    "creates": (deck_doc, creates_methods, {"slide": "s1", "x": 100, "y": 100}),
}


def add_container(app, picture, *, fit=True, where=None, most=(420, 240)):
    make, methods, place = APPS[app]
    doc, desk = make(), RenderDesk(Drawn(*picture))
    params = {**place, **(where or {}), "w": most[0], "h": most[1], "type": "boxer", "source": "x", "fit": fit}
    added = call(doc, methods, "add_container", params, desk)
    asyncio.run(desk.render_into(doc, "ann", added["container"]))
    body = doc.model.get_object(added["object"]).body
    return doc, desk, added, (body.w, body.h)


# ------------------------------------------------------------------------------ what each model says
def test_the_body_text_of_each_app_in_its_own_units():
    assert TextModel().least_new_size() == 20, "12 pt are 16 px, below the 20 every object has at least"
    assert sheet_doc().model.least_new_size() == 20, "13 px, below the 20"
    assert SlideModel.empty().least_new_size() == 40, "40 units of the 1600-wide slide"


def test_a_larger_body_text_makes_the_least_larger():
    model = TextModel()
    css = dict(model.styles.get("body").css)
    model.styles.set_css("body", {**css, "font-size": "24pt"})
    assert model.least_new_size() == 32, "24 pt are 32 px"


def test_the_room_a_new_object_has():
    text = TextModel()
    page = text.page
    across = page.height if page.orientation == "landscape" else page.width
    column = (across - page.margin_left - page.margin_right) / 1000 * 4 / 3
    assert text.room_for_new_object(None) == int(column), "the text column of the page, in CSS pixels"
    deck = Document(SlideModel.empty(), store=MemoryStore())
    call(deck, creates_methods, "add_object", {"slide": "s1", "x": 1000, "y": 10, "kind": "text", "w": 100, "h": 50})
    anchor = next(iter(deck.model.objects.values())).anchor
    assert deck.model.room_for_new_object(anchor) == 600, "the rest of the slide to the right of where it starts"
    assert sheet_doc().model.room_for_new_object(None) is None, "a sheet sets no limit"


# ------------------------------------------------------------------------------ the first picture of a container
@pytest.mark.parametrize(("app", "least", "wide"), [("composes", 20, 100), ("computes", 20, 100), ("creates", 40, 200)])
def test_a_short_formula_is_as_tall_as_the_body_text_with_its_proportions(app, least, wide):
    assert add_container(app, (50, 10))[3] == (wide, least)


@pytest.mark.parametrize("app", ["composes", "computes", "creates"])
def test_a_large_diagram_is_no_larger_than_420_by_240(app):
    assert add_container(app, (1000, 1000))[3] == (240, 240)


def test_a_long_formula_in_composes_is_as_tall_as_the_body_text_and_no_wider_than_the_column():
    assert add_container("composes", (300, 12))[3] == (500, 20), "the least wins over the most of 420"
    doc, desk = text_doc(), RenderDesk(Drawn(300, 12))
    doc.model.styles.set_css("body", {**dict(doc.model.styles.get("body").css), "font-size": "24pt"})
    params = {"paragraph": "b1", "offset": 2, "w": 420, "h": 240, "type": "boxer", "source": "x", "fit": True}
    added = call(doc, composes_methods, "add_container", params, desk)
    asyncio.run(desk.render_into(doc, "ann", added["container"]))
    body = doc.model.get_object(added["object"]).body
    assert (body.w, body.h) == (600, 24), "32 high would be 800 wide; the column of an A4 page is 604"


def test_a_long_formula_on_a_slide_stays_on_the_slide():
    w, h = add_container("creates", (300, 12), where={"x": 1000})[3]
    assert (w, h) == (600, 24), "40 high would be 1000 wide; 600 are left"


@pytest.mark.parametrize("app", ["composes", "computes", "creates"])
def test_only_the_first_picture_is_fitted_and_a_size_i_set_is_kept(app):
    doc, desk, added, _ = add_container(app, (50, 10))
    methods = APPS[app][1]
    shown = doc.model.get_object(added["object"])
    doc.execute(ResizeObject(added["object"], shown.anchor.to_data(), 300, 100), author="ann")
    call(doc, methods, "set_container_source", {"id": added["container"], "source": "again"}, desk)
    asyncio.run(desk.render_into(doc, "ann", added["container"]))
    assert doc.model.get_object(added["object"]).body.w == 300


def test_without_fit_the_frame_given_is_kept():
    assert add_container("creates", (50, 10), fit=False)[3] == (420, 84), "the width stays; the height follows"


# ------------------------------------------------------------------------------ a picture from a file
def png(w, h):
    out = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def add_picture(app, size, *, fit):
    make, methods, place = APPS[app]
    doc = make()
    params = {**place, "w": size[0], "h": size[1], "data": png(*size), "alt": "a dot"}
    params |= {"source_name": "dot.png", "source_path": None, **({"fit": True} if fit else {})}
    added = call(doc, methods, "add_image", params)
    body = doc.model.get_object(added["object"]).body
    return body.w, body.h


@pytest.mark.parametrize(("app", "side"), [("composes", 20), ("computes", 20), ("creates", 40)])
def test_a_tiny_picture_from_a_file_is_as_tall_as_the_body_text_and_square(app, side):
    assert add_picture(app, (8, 8), fit=True) == (side, side)


def test_a_picture_from_a_file_keeps_the_size_the_client_gave_it_when_that_is_within_the_rules():
    assert add_picture("composes", (100, 50), fit=True) == (100, 50)


def test_a_picture_pasted_from_the_object_clipboard_keeps_its_size():
    assert add_picture("composes", (40, 40), fit=False) == (40, 40), "without fit, the size given is the size"
