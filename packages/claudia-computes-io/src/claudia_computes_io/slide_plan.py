"""A workbook's slides in a file (E6.31, D1473): ods and xlsx have no slides, so a slide is written as a sheet.

The sheet a slide becomes has the slide's name (written the way a sheet may be called), stands where the slide stands
among the tabs and has no cells; the objects of the slide hang on it at the cell nearest to where they are, scaled
from the slide's 1600 × 900 units to the size a chart tab is written at, so the charts and pictures of a slide are
written by the very code that writes those of a sheet. The export says so for each slide (the loss ``slide``, with its
name). Read back, what was a slide is a sheet (Q15 of the chart session).
"""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, Sheet
from claudia_core import SLIDE_HEIGHT, SLIDE_WIDTH
from claudia_odf_io import Loss

from .xlsx_charts import TAB_SIZE, sheet_name

#: How much smaller a slide's objects are on the sheet it becomes: the whole slide fits the size a chart tab is
#: written at, keeping its proportions.
SLIDE_SCALE = min(TAB_SIZE[0] / SLIDE_WIDTH, TAB_SIZE[1] / SLIDE_HEIGHT)


def slide_losses(model: WorkbookModel) -> tuple[Loss, ...]:
    """One loss ``slide`` for each slide of ``model``, with its name, in the order of the tabs: "The slide “…” was
    written as a sheet: a workbook in this format has no slides." """
    return tuple(Loss("slide", model.thing_name(slide_id), 1) for slide_id in model.slide_ids())


def with_slides_as_sheets(model: WorkbookModel) -> WorkbookModel:
    """``model`` itself when it has no slides; else a copy of it in which every slide is a sheet without cells, in the
    slide's place among the tabs, with the slide's objects on it (see the module description). The copy is what a file
    is written from; ``model`` does not change."""
    slide_ids = model.slide_ids()
    if not slide_ids:
        return model
    state = model.serialize()
    taken = {sheet.name.casefold() for sheet in model.sheets.values()}
    names = {slide_id: sheet_name(model.thing_name(slide_id), taken) for slide_id in slide_ids}
    sheets = {item["id"]: item for item in state["sheets"]}
    state["sheets"] = [
        sheets[tab.id] if tab.kind == "sheet" else Sheet(SheetId(tab.id), names[tab.id]).to_data() for tab in model.tabs
    ]
    state["tabs"] = [{"kind": "sheet", "id": tab.id} for tab in model.tabs]
    state["slides"] = []
    state["objects"] = [_on_a_sheet(item, model.min_object_size) for item in state["objects"]]
    return WorkbookModel.restore(state)


def _on_a_sheet(item: dict, smallest: int) -> dict:
    """An object as plain data, hung at a cell if it sat on a slide."""
    anchor = item["anchor"]
    if anchor["kind"] != "slide":
        return item
    return {
        **item,
        "w": max(smallest, round(item["w"] * SLIDE_SCALE)),
        "h": max(smallest, round(item["h"] * SLIDE_SCALE)),
        "anchor": {
            "kind": "cell",
            "holder": anchor["holder"],
            "row": round(anchor["y"] * SLIDE_SCALE / DEFAULT_ROW_HEIGHT),
            "col": round(anchor["x"] * SLIDE_SCALE / DEFAULT_COL_WIDTH),
        },
    }
