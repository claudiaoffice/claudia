"""One asset store for what objects show and the document keeps once, by id (D1431).

An image, a shape's outline, a chart's definition (``diagram``) and a container's definition (``rendering``) are
defined, changed and forgotten through the same three commands, in every app. A small model with one page is enough to
show it; each app's own tests show its objects on top of this."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Self

import pytest

from claudia_core import (
    AddObject,
    AssetsChanged,
    DefineAsset,
    Document,
    DocumentModel,
    ForgetAsset,
    ObjectBody,
    ObjectModel,
    RenderedDefinition,
    ShapeDefinition,
    UpdateAsset,
    paragraph_for,
)
from claudia_core.assets import decode_image
from claudia_core.commands import core_commands


# ----------------------------------------------------------------------------- a page that holds objects
@dataclass(frozen=True)
class Spot:
    """Where an object is on the one page of the test model."""

    kind: ClassVar[str] = "spot"
    x: int
    y: int

    @property
    def container(self) -> str:
        return "page"

    def to_data(self) -> dict:
        return {"kind": self.kind, "x": self.x, "y": self.y}


@dataclass(frozen=True)
class Pie:
    """A chart definition of the test model: what the kernel keeps without reading it."""

    id: str
    label: str = ""

    def to_data(self) -> dict:
        return {"id": self.id, "label": self.label}


class PageModel(DocumentModel, ObjectModel[Spot]):
    app: ClassVar[str] = "test-page"
    registry = core_commands

    def __init__(self) -> None:
        ObjectModel.__init__(self)
        self.open_container("page")

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"objects": self.objects_to_data(), "assets": self.assets_to_data()}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.restore_objects(state["objects"], state["assets"])
        return model

    def containers(self):
        return ["page"]

    def check_anchor(self, anchor: Spot, body: ObjectBody) -> None:
        if anchor.x < 0 or anchor.y < 0:
            raise ValueError("off the page")

    def anchor_from_data(self, data: dict) -> Spot:
        return Spot(data["x"], data["y"])

    def diagram_from_data(self, data: dict) -> Pie:
        return Pie(data["id"], data.get("label", ""))

    @classmethod
    def blank_diagram(cls, definition: dict) -> dict:
        return {**definition, "label": ""}


@pytest.fixture
def doc() -> Document:
    return Document(PageModel())


def picture():
    return decode_image(b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="20"/>')


#: One asset of each kind, as plain data, and the model's own view of that kind.
ASSETS = {
    "image": (lambda: picture().to_data(), lambda m: m.images),
    "shape": (lambda: ShapeDefinition("star", "Star", "M0 0 L100 100 Z").to_data(), lambda m: m.shapes),
    "diagram": (lambda: {"id": "pie1", "label": "Sales"}, lambda m: m.diagrams),
    "rendering": (
        lambda: RenderedDefinition("r1", "mermaid", "flowchart LR\n  A --> B").to_data(),
        lambda m: m.renderings,
    ),
}
KINDS = list(ASSETS)


def heard(doc: Document) -> list[dict]:
    """What the document tells the clients about its assets, as they receive it."""
    events: list[dict] = []
    doc.subscribe(lambda event: events.append(event.to_data()) if isinstance(event, AssetsChanged) else None)
    return events


# ----------------------------------------------------------------------------- define, undo, redo
@pytest.mark.parametrize("kind", KINDS)
def test_a_defined_asset_is_kept_announced_and_undone_and_redone(doc, kind):
    data, view = ASSETS[kind][0](), ASSETS[kind][1]
    events = heard(doc)

    doc.execute(DefineAsset(kind, data), author="ann")

    assert view(doc.model)[data["id"]].to_data() == data
    assert events[-1]["type"] == kind and events[-1]["id"] == data["id"]
    doc.undo("ann")
    assert data["id"] not in view(doc.model)
    assert events[-1] == {"type": kind, "id": data["id"], ("asset" if kind == "image" else "definition"): None}
    doc.redo("ann")
    assert view(doc.model)[data["id"]].to_data() == data


def show(doc: Document, kind: str, ref: str, object_id: str = "o1", author: str = "ann"):
    """Put an object on the page that shows the asset ``ref`` of ``kind``."""
    object_kind = {"rendering": "rendered"}.get(kind, kind)
    extra = {"paragraph": paragraph_for("", "plain")} if kind == "shape" else {}
    if kind == "image":
        from claudia_core.assets import ImageImport

        extra = {"imported": ImageImport(ref, "a picture", "ann", "2026-11-21T10:00:00Z", "disk", "pic.svg")}
    w = 20 if kind == "image" else 40  # the picture is 10 by 20 and keeps its proportions
    body = ObjectBody(object_id, object_kind, w, 40, "plain", ref=ref, **extra)
    doc.execute(AddObject(body, Spot(1, 1).to_data()), author=author)


# ----------------------------------------------------------------------------- what is in use stays
@pytest.mark.parametrize("kind", KINDS)
def test_an_asset_an_object_shows_cannot_be_forgotten(doc, kind):
    data = ASSETS[kind][0]()
    doc.execute(DefineAsset(kind, data), author="ann")
    show(doc, kind, data["id"])

    with pytest.raises(ValueError, match=f"{kind} '{data['id']}' is in use by 'o1'"):
        doc.execute(ForgetAsset(kind, data["id"]), author="ann")


def test_a_picture_a_container_shows_cannot_be_forgotten(doc):
    image = picture()
    doc.execute(DefineAsset("image", image.to_data()), author="ann")
    doc.execute(DefineAsset("rendering", ASSETS["rendering"][0]() | {"image": image.id}), author="ann")

    with pytest.raises(ValueError, match="is in use by 'r1'"):
        doc.execute(ForgetAsset("image", image.id), author="ann")


def test_a_container_cannot_show_a_picture_the_document_does_not_have(doc):
    missing = "a" * 64  # the form of an image's id, which no image here has
    with pytest.raises(ValueError, match=f"does not know the image '{missing}'"):
        doc.execute(DefineAsset("rendering", ASSETS["rendering"][0]() | {"image": missing}), author="ann")


def test_undoing_a_definition_is_refused_once_a_colleague_shows_it(doc):
    data = ASSETS["shape"][0]()
    doc.execute(DefineAsset("shape", data), author="ann")
    show(doc, "shape", data["id"], author="ben")

    with pytest.raises(Exception, match="(?i)undo"):
        doc.undo("ann")
    assert data["id"] in doc.model.shapes


# ----------------------------------------------------------------------------- changed in place
@pytest.mark.parametrize(
    ("kind", "change"),
    [("diagram", {"label": "Costs"}), ("rendering", {"source": "flowchart TB\n  B --> A"})],
)
def test_a_chart_or_a_container_is_changed_in_place_and_the_undo_puts_it_back(doc, kind, change):
    data, view = ASSETS[kind][0](), ASSETS[kind][1]
    doc.execute(DefineAsset(kind, data), author="ann")

    doc.execute(UpdateAsset(kind, data["id"], data | change), author="ann")
    assert view(doc.model)[data["id"]].to_data() == data | change
    doc.undo("ann")
    assert view(doc.model)[data["id"]].to_data() == data


@pytest.mark.parametrize("kind", ["image", "shape"])
def test_a_picture_or_an_outline_is_not_changed_in_place(doc, kind):
    data = ASSETS[kind][0]()
    doc.execute(DefineAsset(kind, data), author="ann")

    with pytest.raises(ValueError, match="not changed in place"):
        doc.execute(UpdateAsset(kind, data["id"], data), author="ann")


def test_a_container_keeps_its_type(doc):
    data = ASSETS["rendering"][0]()
    doc.execute(DefineAsset("rendering", data), author="ann")

    with pytest.raises(ValueError, match="cannot change its type"):
        doc.execute(UpdateAsset("rendering", "r1", data | {"type": "latex"}), author="ann")


def test_a_table_has_commands_of_its_own(doc):
    with pytest.raises(ValueError, match="table commands"):
        doc.execute(DefineAsset("table", {"id": "t1"}), author="ann")


# ----------------------------------------------------------------------------- stored and redacted
def test_every_kind_is_stored_and_read_back(doc):
    for kind in KINDS:
        doc.execute(DefineAsset(kind, ASSETS[kind][0]()), author="ann")

    again = PageModel.restore(doc.model.serialize())

    for kind in KINDS:
        data, view = ASSETS[kind][0](), ASSETS[kind][1]
        assert view(again)[data["id"]].to_data() == data


def test_a_redacted_definition_keeps_no_words_but_the_kind_and_the_id():
    rendering = DefineAsset("rendering", ASSETS["rendering"][0]()).redacted_in(PageModel)
    chart = DefineAsset("diagram", {"id": "pie1", "label": "Sales"}).redacted_in(PageModel)
    shape = DefineAsset("shape", ASSETS["shape"][0]())

    assert rendering.data["source"] == "" and rendering.data["id"] == "r1"
    assert chart.data == {"id": "pie1", "label": ""}
    assert shape.redacted_in(PageModel) == shape
