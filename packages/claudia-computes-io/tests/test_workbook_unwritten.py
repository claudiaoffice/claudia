"""ods_unwritten_changes / xlsx_unwritten_changes: what changed in a workbook that the converters do not write
(D299, D405). Cells and their looks are written; widths and heights, names, charts and floating objects are not."""

from __future__ import annotations

import pytest
from claudia_computes_io import (
    ods_export_losses,
    ods_unwritten_changes,
    xlsx_export_losses,
    xlsx_unwritten_changes,
)

from claudia_computes import (
    CellAnchor,
    CellRef,
    ChartSpec,
    ObjectBody,
    RangeRef,
    Sheet,
    SheetId,
    VisualObject,
    WorkbookModel,
)
from claudia_core import Paragraph
from claudia_odf_io import Loss

BOTH = pytest.mark.parametrize("unwritten", [ods_unwritten_changes, xlsx_unwritten_changes])


def a_workbook() -> WorkbookModel:
    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "Data")
    model.add_sheet(sheet, None)
    sheet.cells[(0, 0)] = {"t": "int", "v": 1}
    return model


@BOTH
def test_a_workbook_that_did_not_change_has_no_unwritten_changes(unwritten):
    assert unwritten(a_workbook(), a_workbook()) == ()


@BOTH
def test_edited_cells_are_written_so_they_are_no_loss(unwritten):
    after = a_workbook()
    after.sheets[SheetId("s1")].cells[(1, 1)] = {"t": "text", "v": "new"}
    assert unwritten(after, a_workbook()) == ()


@BOTH
def test_column_widths_and_row_heights_are_written_so_they_are_no_loss(unwritten):
    after = a_workbook()
    after.sheets[SheetId("s1")].col_widths[0] = 120.0
    after.sheets[SheetId("s1")].row_heights[1] = 40.0
    assert unwritten(after, a_workbook()) == ()


def a_chart_spec() -> ChartSpec:
    one = CellRef(0, 0, SheetId("s1"))
    return ChartSpec(id="spec", kind="bar", range=RangeRef(one, one))


@BOTH
def test_a_chart_floating_on_a_sheet_is_written_so_it_is_no_loss(unwritten):
    after = a_workbook()
    after.diagrams.define(a_chart_spec())
    body = ObjectBody("o1", "diagram", 200, 100, "plain-image", ref="spec")
    after.insert_object(VisualObject(body, CellAnchor(SheetId("s1"), 3, 3)))
    assert unwritten(after, a_workbook()) == ()


@BOTH
def test_a_floating_object_is_not_written(unwritten):
    after = a_workbook()
    box = ObjectBody("o1", "text", 100, 100, "plain-box", Paragraph("p1", "note"))
    after.insert_object(VisualObject(box, CellAnchor(SheetId("s1"), 0, 0)))
    assert unwritten(after, a_workbook()) == (Loss("object", "", 1),)


@BOTH
def test_a_fresh_export_compares_with_an_empty_workbook(unwritten):
    model = a_workbook()
    model.sheets[SheetId("s1")].row_heights[2] = 40.0
    box = ObjectBody("o1", "text", 100, 100, "plain-box", Paragraph("p1", "note"))
    model.insert_object(VisualObject(box, CellAnchor(SheetId("s1"), 0, 0)))
    assert unwritten(model) == (Loss("object", "", 1),)


def test_the_export_loss_lists_say_what_the_converters_do_not_write():
    model = a_workbook()
    body = ObjectBody("o1", "diagram", 200, 100, "plain-image", ref="spec")
    model.diagrams.define(a_chart_spec())
    model.insert_object(VisualObject(body, CellAnchor(SheetId("s1"), 3, 3)))
    model.diagrams.put(ChartSpec(id="spec", kind="bar", source="Gone"))
    assert Loss("chart", "empty", 1) in ods_export_losses(model)  # (a chart with nothing to draw)
    assert Loss("chart", "empty", 1) in xlsx_export_losses(model)
