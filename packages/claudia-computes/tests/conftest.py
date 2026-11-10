import struct

import pytest

from claudia_computes import (
    AddObject,
    AddSheet,
    CellAnchor,
    CellRef,
    ChartSpec,
    DefineDiagram,
    DefineImage,
    MoveObject,
    ObjectBody,
    RangeRef,
    ResizeObject,
    SheetId,
    SheetObject,
    VisualObject,
    WorkbookModel,
)
from claudia_core import Batch, CommandLog, Document, ImageAsset, ImageImport, MemoryStore, decode_image
from claudia_core.testing import FakeClock

S1 = "s1"


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def doc(clock):
    d = Document(WorkbookModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def reopen(doc):
    """A second document built from a copy of the log, to compare with the live one."""
    return Document.open(WorkbookModel, CommandLog.from_data(doc.log.to_data(), WorkbookModel.registry))


def image_asset(width: int = 40, height: int = 20) -> ImageAsset:
    """A tiny, valid GIF, decoded through the real decoder (no pixels, just a header the test needs)."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01\x00\x00"
    return decode_image(header + frame + b"\x3b")


def image_import(
    asset_id: str, *, imported_by: str = "ana", source_path: str | None = "/Users/ana/pic.gif"
) -> ImageImport:
    return ImageImport.from_data(
        {
            "asset": asset_id,
            "alt": "a sample picture",
            "imported_by": imported_by,
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": source_path,
        }
    )


def image_object(object_id: str = "i1", sheet: str = S1, asset: ImageAsset | None = None, **changes) -> SheetObject:
    asset = asset or image_asset()
    fields = {
        "id": object_id,
        "sheet": sheet,
        "kind": "image",
        "row": 2,
        "col": 2,
        "w": 400,
        "h": 200,
        "style": "plain-image",
        "image": asset.id,
        "imported": image_import(asset.id),
    }
    return build(**{**fields, **changes})


def build(**fields) -> SheetObject:
    """A :class:`SheetObject` from flat fields: the body's go to the body, ``sheet``/``row``/``col`` to the
    anchor. The helpers keep the flat signatures the tests have always used, while the model holds the two
    halves apart (E10.16)."""
    anchor = CellAnchor(SheetId(fields.pop("sheet", S1)), fields.pop("row", 0), fields.pop("col", 0))
    return VisualObject(ObjectBody(**fields), anchor)


# -- the shared commands, built the way a client does: a body, and the anchor as plain data -------------------
def add(obj: SheetObject, at: int | None = None) -> AddObject:
    """``AddObject`` for a built object."""
    return AddObject(obj.body, obj.anchor.to_data(), at)


def move(object_id: str, row: int, col: int, sheet: str = S1) -> MoveObject:
    """``MoveObject`` to an anchor cell."""
    return MoveObject(object_id, CellAnchor(SheetId(sheet), row, col).to_data())


def resize(object_id: str, row: int, col: int, w: int, h: int, sheet: str = S1) -> ResizeObject:
    """``ResizeObject`` to an anchor cell and a pixel size."""
    return ResizeObject(object_id, CellAnchor(SheetId(sheet), row, col).to_data(), w, h)


def frame(doc, object_id: str) -> tuple[int, int, int, int]:
    """``(row, col, w, h)`` of an object: the anchor's cell and the body's size."""
    obj = doc.model.get_object(object_id)
    return (obj.anchor.row, obj.anchor.col, obj.body.w, obj.body.h)


def put_image(doc, object_id: str = "i1", author: str = "ana", asset: ImageAsset | None = None, **changes):
    """Add an image object, defining its asset first if the document does not already have it.

    Returns what ``doc.execute`` returns — read the object back with ``doc.model.get_object(object_id)``."""
    asset = asset or image_asset()
    obj = image_object(object_id, asset=asset, **changes)
    steps = [add(obj)] if asset.id in doc.model.images else [DefineImage(asset), add(obj)]
    return doc.execute(steps[0] if len(steps) == 1 else Batch(tuple(steps)), author=author)


# -- charts (E6.6): a ChartSpec plus either a tab or a floating diagram object, or both ------------------------
def chart_spec(spec_id: str = "c1", *, sheet: str = S1, first=(0, 0), last=(2, 1), **changes) -> ChartSpec:
    """A minimal, valid bar chart over ``sheet``'s cells from ``first`` to ``last`` (row, col), inclusive."""
    range_ = RangeRef(CellRef(first[0], first[1], SheetId(sheet)), CellRef(last[0], last[1], SheetId(sheet)))
    fields = {"id": spec_id, "kind": "bar", "range": range_}
    return ChartSpec(**{**fields, **changes})


def diagram_object(object_id: str = "d1", sheet: str = S1, spec_id: str = "c1", **changes) -> SheetObject:
    """A floating diagram object (E6.6) showing the definition ``spec_id`` names."""
    fields = {
        "id": object_id,
        "sheet": sheet,
        "kind": "diagram",
        "row": 2,
        "col": 2,
        "w": 400,
        "h": 200,
        "style": "plain-image",  # a diagram carries its own colours, same as an image (plain-image's own purpose)
        "diagram": spec_id,
    }
    return build(**{**fields, **changes})


def put_chart_spec(doc, spec_id: str = "c1", author: str = "ana", **changes) -> ChartSpec:
    """Register a chart definition (``DefineDiagram``), defining it first if the document does not have it.

    Returns the spec — read it back with ``doc.model.diagrams[spec_id]``."""
    spec = chart_spec(spec_id, **changes)
    if spec_id not in doc.model.diagrams:
        doc.execute(DefineDiagram(spec.to_data()), author=author)
    return spec
