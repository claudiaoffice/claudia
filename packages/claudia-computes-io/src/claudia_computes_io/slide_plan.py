"""A workbook's slides in a file (E6.31, D1473): ods and xlsx have no slides, so a slide is written as a sheet.

The sheet a slide becomes has the slide's name (written the way a sheet may be called in Excel, the stricter of the two
formats), what was written about it, and the slide's place among the tabs; it has no cells. The objects of the slide
hang on it at the cell nearest to where they are, scaled from the slide's 1600 × 900 units to the size a chart tab is
written at, so the charts and pictures of a slide are written by the very code that writes those of a sheet. The export
says so for each slide (the loss ``slide``, with its name). Read back, what was a slide is a sheet (D1473).
"""

from __future__ import annotations

from dataclasses import replace

from claudia_computes import CellAnchor, SheetId, VisualObject, WorkbookModel
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, Sheet
from claudia_core import SLIDE_HEIGHT, SLIDE_WIDTH, SlideAnchor
from claudia_odf_io import Loss

from .xlsx_charts import TAB_SIZE, sheet_name

#: How much smaller a slide's objects are on the sheet it becomes: the whole slide fits the size a chart tab is
#: written at, keeping its proportions.
SLIDE_SCALE = min(TAB_SIZE[0] / SLIDE_WIDTH, TAB_SIZE[1] / SLIDE_HEIGHT)


def slide_losses(model: WorkbookModel) -> tuple[Loss, ...]:
    """One loss ``slide`` for each slide of ``model``, with its name, in the order of the tabs: the slide was written as
    a sheet, since a workbook in this format has no slides."""
    return tuple(Loss("slide", model.thing_name(slide_id), 1) for slide_id in model.slide_ids())


def with_slides_as_sheets(model: WorkbookModel) -> WorkbookModel:
    """What a file is written from: a workbook in which every slide of ``model`` is a sheet without cells (see the
    module description), or ``model`` itself when it has none. ``model`` does not change."""
    if not model.slide_ids():
        return model
    copy = WorkbookModel.restore(model.serialize())
    taken = {sheet.name.casefold() for sheet in copy.sheets.values()}
    for slide_id in copy.slide_ids():
        objects = copy.objects_on(slide_id)
        for obj in objects:
            copy.delete_object(obj.id)
        place = copy.tab_index(slide_id)
        slide, _ = copy.remove_slide(slide_id)
        copy.add_sheet(Sheet(SheetId(slide_id), sheet_name(slide.name, taken)), place)
        copy.set_thing_description(slide_id, slide.description)
        for obj in objects:
            copy.insert_object(_on_a_sheet(obj, copy.min_object_size), shared_names=False)
    return copy


def _on_a_sheet(obj: VisualObject, smallest: int) -> VisualObject:
    """An object of a slide, hung at the nearest cell of the sheet the slide becomes and scaled with it; one that would
    be smaller than ``smallest`` on a side is scaled less, so that it keeps its proportions (a picture must)."""
    anchor = obj.anchor
    assert isinstance(anchor, SlideAnchor)  # (the objects of a slide)
    scale = max(SLIDE_SCALE, smallest / max(1, min(obj.body.w, obj.body.h)))
    body = replace(obj.body, w=round(obj.body.w * scale), h=round(obj.body.h * scale))
    cell = CellAnchor(
        SheetId(anchor.holder),
        round(anchor.y * SLIDE_SCALE / DEFAULT_ROW_HEIGHT),
        round(anchor.x * SLIDE_SCALE / DEFAULT_COL_WIDTH),
    )
    return VisualObject(body, cell)
