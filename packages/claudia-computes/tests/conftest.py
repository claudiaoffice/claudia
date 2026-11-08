import struct

import pytest

from claudia_computes import AddObject, AddSheet, DefineImage, SheetObject, WorkbookModel
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
        "image": asset.id,
        "imported": image_import(asset.id),
    }
    return SheetObject(**{**fields, **changes})


def put_image(doc, object_id: str = "i1", author: str = "ana", asset: ImageAsset | None = None, **changes):
    """Add an image object, defining its asset first if the document does not already have it.

    Returns what ``doc.execute`` returns — read the object back with ``doc.model.get_object(object_id)``."""
    asset = asset or image_asset()
    obj = image_object(object_id, asset=asset, **changes)
    steps = [AddObject(obj)] if asset.id in doc.model.images else [DefineImage(asset), AddObject(obj)]
    return doc.execute(steps[0] if len(steps) == 1 else Batch(tuple(steps)), author=author)
