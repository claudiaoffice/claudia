"""Two bar charts LibreOffice saved (a titled one over the columns of a table, one over its rows), each an embedded
``Object N`` with a preview picture, pinned to a cell of the data sheet. Both come in as diagrams with a floating
object. One is moved and resized, one is added; the chart nobody touched comes back byte for byte (D462)."""

from __future__ import annotations

from dataclasses import replace

from claudia_computes import CellAnchor, ChartSpec, ObjectBody, SheetId, VisualObject, WorkbookModel
from claudia_test_documents.case import Case

DATA = SheetId("s1")


def import_checks(model: WorkbookModel) -> None:
    first, second = model.diagrams["c1"], model.diagrams["c2"]
    assert isinstance(first, ChartSpec) and isinstance(second, ChartSpec)
    assert (first.title, first.x_title, first.y_title, first.series_in) == ("Sales", "Region", "Euro", "columns")
    assert (second.series_in, second.legend) == ("rows", False)
    assert model.objects["o1"].anchor == CellAnchor(DATA, 6, 1)
    assert model.objects["o2"].anchor == CellAnchor(DATA, 6, 8)
    assert (model.objects["o1"].body.w, model.objects["o1"].body.h) == (480, 300)


def modify(model: WorkbookModel) -> WorkbookModel:
    moved = model.objects["o1"]
    model.replace_object(VisualObject(replace(moved.body, w=600, h=240), CellAnchor(DATA, 12, 1)))
    model.diagrams.define(replace(model.diagrams["c1"], id="c9", title="Another", series_in="rows"))
    body = ObjectBody("o9", "diagram", 300, 200, "plain-image", ref="c9", description="Sales by region")
    model.insert_object(VisualObject(body, CellAnchor(DATA, 20, 1)))
    return model


def after_checks(model: WorkbookModel) -> None:
    assert len(model.objects) == 3
    moved = next(obj for obj in model.objects.values() if obj.body.w == 600)
    assert (moved.anchor, moved.body.h) == (CellAnchor(DATA, 12, 1), 240)
    added = next(obj for obj in model.objects.values() if obj.body.w == 300)
    assert (added.anchor, added.body.description) == (CellAnchor(DATA, 20, 1), "Sales by region")
    assert model.diagrams[added.body.diagram].title == "Another"
    untouched = next(obj for obj in model.objects.values() if obj.anchor == CellAnchor(DATA, 6, 8))
    assert model.diagrams[untouched.body.diagram].series_in == "rows"


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=[
        "Object 2/content.xml",
        "Object 2/styles.xml",
        "ObjectReplacements/Object 2",
        "Object 1/content.xml",
    ],
)
