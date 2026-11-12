"""A chart (LibreOffice-written) is an embedded sub-document (``Object 1/…``) with a preview picture
(``ObjectReplacements/Object 1``), placed by a frame in a cell of the second sheet. The edit changes a cell of
the chart's source data; the chart's parts and the frame that places it come back byte for byte (D413). The chart
itself is not in the model, the import reports it as a loss."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Data", "Chart"]
    assert model.sheets[SheetId("s1")].cells[(0, 0)] == {"t": "text", "v": "Region"}
    assert model.sheets[SheetId("s1")].cells[(1, 1)] == {"t": "int", "v": 100}
    assert model.sheets[SheetId("s2")].cells == {}


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheets[SheetId("s1")], 1, 1, {"t": "int", "v": 999})
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.sheets[SheetId("s1")].cells[(1, 1)] == {"t": "int", "v": 999}
    assert model.sheets[SheetId("s2")].cells == {}


def frame_is_untouched(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    frame = before[before.index("<draw:frame") : before.index("</draw:frame>")]
    assert frame in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=[
        "Object 1/content.xml",
        "Object 1/styles.xml",
        "Object 1/meta.xml",
        "ObjectReplacements/Object 1",
        "META-INF/manifest.xml",
    ],
    preserve_elements=frame_is_untouched,
)
