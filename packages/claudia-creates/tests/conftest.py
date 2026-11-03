import pytest

from claudia_core import Batch, CommandLog, Document, MemoryStore
from claudia_core.testing import FakeClock
from claudia_creates import AddObject, DefineShape, ShapeLibrary, SlideModel, SlideObject

SLIDE = "s1"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def doc(clock):
    return Document(SlideModel.empty(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)


def text_box(object_id: str = "t1", **changes) -> SlideObject:
    fields = {"id": object_id, "slide": SLIDE, "kind": "text", "x": 100, "y": 100, "w": 400, "h": 120}
    return SlideObject(**{"style": "body-text", **fields, **changes})


def shape_object(object_id: str = "r1", shape: str = "rectangle", **changes) -> SlideObject:
    fields = {"id": object_id, "slide": SLIDE, "kind": "shape", "shape": shape, "x": 200, "y": 200, "w": 300, "h": 200}
    return SlideObject(**{"style": "plain-shape", **fields, **changes})


def define(shape_id: str = "rectangle") -> DefineShape:
    shape = ShapeLibrary.load().get(shape_id)
    assert shape is not None
    return DefineShape(shape)


def put(doc, obj: SlideObject, author: str = "ana"):
    """Add an object; a shape object brings its definition along, as the server does."""
    if obj.shape is not None and obj.shape not in doc.model.shapes:
        return doc.execute(Batch((define(obj.shape), AddObject(obj))), author=author)
    return doc.execute(AddObject(obj), author=author)


def reopen(doc):
    """A second document built from a copy of the log, to compare with the live one."""
    return Document.open(SlideModel, CommandLog.from_data(doc.log.to_data(), SlideModel.registry))
