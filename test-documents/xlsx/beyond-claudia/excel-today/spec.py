"""What Excel writes today and the model does not hold (D370, D371): a spilled ``SEQUENCE`` with the ``cm`` mark that
makes it spill and the workbook's ``metadata.xml`` behind that mark, a list in ``D1`` that takes its choices from
another sheet, and an icon set -- the last two live in the worksheet's ``extLst``, which openpyxl drops when it saves.
A shared formula fills ``B1:B3``.

The spilled cells come in as their values (the model cannot spill ``SEQUENCE``); the shared formula as each cell's own.
Editing ``A2`` -- on the same sheet as all of it -- must leave the ``extLst``, the spill and its mark exactly as they
were."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from lxml import etree

from claudia_computes import SheetId, WorkbookModel
from claudia_test_documents.case import Case

X = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def import_checks(model: WorkbookModel) -> None:
    plan = model.sheets[SheetId("s1")]
    assert [plan.cells[(r, 2)] for r in range(3)] == [{"t": "int", "v": n} for n in (1, 2, 3)]
    assert plan.cells[(1, 1)] == {"t": "formula", "v": "=A2*2"}
    assert plan.cells[(0, 3)] == {"t": "text", "v": "Apple"}


def modify(model: WorkbookModel) -> WorkbookModel:
    plan = model.sheets[SheetId("s1")]
    model.store(plan, 1, 0, {"t": "int", "v": 20})
    return model


def after_checks(model: WorkbookModel) -> None:
    plan = model.sheets[SheetId("s1")]
    assert plan.cells[(1, 0)] == {"t": "int", "v": 20}
    assert plan.grid.get((1, 1)) == 40
    assert [plan.cells[(r, 2)]["v"] for r in range(3)] == [1, 2, 3]


def _plan(data: bytes) -> etree._Element:
    with ZipFile(BytesIO(data)) as zf:
        return etree.fromstring(zf.read("xl/worksheets/sheet1.xml"))


def preserve_elements(original: bytes, exported: bytes) -> None:
    before, after = _plan(original), _plan(exported)
    assert etree.tostring(before.find("x:extLst", X)) == etree.tostring(after.find("x:extLst", X))
    for ref in ("C1", "C2", "C3", "D1"):
        cell = f"x:sheetData/x:row/x:c[@r='{ref}']"
        assert etree.tostring(before.find(cell, X)) == etree.tostring(after.find(cell, X))


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["xl/metadata.xml", "xl/worksheets/sheet2.xml"],
    preserve_elements=preserve_elements,
)
