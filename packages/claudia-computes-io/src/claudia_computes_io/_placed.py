"""Where everything of a workbook is in an xlsx or ods file (E6.31, D1477): its tabs, and each object on its tab.

Neither format has slides, so a slide is a tab of its own, in its place among the sheets, without cells, named the way a
sheet may be called in Excel (the stricter of the two formats). Its objects are where they are on the slide: one unit
of the slide is :attr:`SlideSize.px_per_unit` pixels of the tab, one by default, so that a slide of 1600 × 900 covers
1600 × 900 pixels from the corner of the tab. The size is a setting of the export, not a constant, so that a person
can one day be asked for it.

Both formats take their tabs, charts and pictures from here (:mod:`._charts`, :mod:`._pictures`) and differ only in
how a file says where a drawing is: xlsx by the cell its corner is in and how far into it (:attr:`Placed.pin`), ods by
its distance from the corner of the tab (:attr:`Placed.x`, :attr:`Placed.y`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from claudia_computes import CellAnchor, SheetId, VisualObject, WorkbookModel
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.model import DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, Sheet
from claudia_core import SlideAnchor
from claudia_odf_io import xml_safe


@dataclass(frozen=True)
class SlideSize:
    """How big a slide is on its tab: pixels of the tab to one unit of the slide (D1477)."""

    px_per_unit: float = 1.0


#: The size a slide is written at when the export asks for none: one pixel to a unit.
ONE_TO_ONE = SlideSize()


@dataclass(frozen=True)
class FileTab:
    """A tab of the file: a sheet of the workbook, or a slide written as a tab without cells."""

    id: SheetId
    #: The name the file gives it: a sheet's own, a slide's as a sheet may be called in Excel.
    name: str
    is_slide: bool

    def sheet(self, model: WorkbookModel) -> Sheet:
        """What is written for the tab: the sheet itself, or for a slide a sheet without cells by its name."""
        return Sheet(self.id, self.name) if self.is_slide else model.sheets[self.id]


@dataclass(frozen=True)
class Pin:
    """Where the corner of a drawing is in cells: the cell it is in, and how far into it, in pixels."""

    row: int
    col: int
    dx: float = 0.0
    dy: float = 0.0


@dataclass(frozen=True)
class Placed:
    """One object of the workbook on its tab: where its corner is, in pixels from the corner of the tab and as a
    :class:`Pin`, how big it is in pixels, and its place in the stack of its tab (the last is in front)."""

    obj: VisualObject
    tab: FileTab
    x: float
    y: float
    width: float
    height: float
    pin: Pin
    layer: int


def tab_name(wanted: str, taken: set[str]) -> str:
    """A name for the tab a slide becomes: ``wanted`` as a sheet may be called in Excel (at most 31 characters, none
    of ``[]*?:/\\``), and one no tab in ``taken`` has (folded); it is added to ``taken``."""
    name = re.sub(r"[\[\]*?:/\\]", "-", xml_safe(wanted)).strip("' ")[:31] or "Slide"
    candidate, number = name, 1
    while candidate.casefold() in taken:
        number += 1
        suffix = f" ({number})"
        candidate = name[: 31 - len(suffix)] + suffix
    taken.add(candidate.casefold())
    return candidate


def file_tabs(model: WorkbookModel) -> tuple[FileTab, ...]:
    """The tabs of the file, in the order of the workbook's tabs."""
    taken = {sheet.name.casefold() for sheet in model.sheets.values()}
    return tuple(
        FileTab(SheetId(tab.id), model.sheets[SheetId(tab.id)].name, is_slide=False)
        if tab.kind == "sheet"
        else FileTab(SheetId(tab.id), tab_name(model.slides[tab.id].name, taken), is_slide=True)
        for tab in model.tabs
    )


def cell_at(widths: Mapping[int, float], heights: Mapping[int, float], x: float, y: float) -> Pin:
    """The cell ``x`` and ``y`` pixels from the corner of a sheet are in, by its widths and heights (the inverse of
    :func:`offset_of`), and how far into it."""
    column = row = 0
    left = top = 0.0
    while column < MAX_COLS - 1 and left + widths.get(column, DEFAULT_COL_WIDTH) <= x:
        left += widths.get(column, DEFAULT_COL_WIDTH)
        column += 1
    while row < MAX_ROWS - 1 and top + heights.get(row, DEFAULT_ROW_HEIGHT) <= y:
        top += heights.get(row, DEFAULT_ROW_HEIGHT)
        row += 1
    return Pin(row, column, x - left, y - top)


def offset_of(widths: Mapping[int, float], heights: Mapping[int, float], row: int, col: int) -> tuple[float, float]:
    """Where the corner of a cell is, in pixels from the corner of the sheet (the inverse of :func:`cell_at`)."""
    left = sum(widths.get(column, DEFAULT_COL_WIDTH) for column in range(col))
    top = sum(heights.get(line, DEFAULT_ROW_HEIGHT) for line in range(row))
    return left, top


def placed_object(
    model: WorkbookModel, obj: VisualObject, tab: FileTab, layer: int = 0, size: SlideSize = ONE_TO_ONE
) -> Placed:
    """``obj`` on ``tab``: an object of a sheet at the corner of its cell, one of a slide where it is on the slide."""
    anchor, body = obj.anchor, obj.body
    if isinstance(anchor, CellAnchor):
        sheet = model.sheets[anchor.sheet]
        x, y = offset_of(sheet.col_widths, sheet.row_heights, anchor.row, anchor.col)
        return Placed(obj, tab, x, y, body.w, body.h, Pin(anchor.row, anchor.col), layer)
    assert isinstance(anchor, SlideAnchor)  # (a workbook's objects are on sheets and slides)
    scale = size.px_per_unit
    x, y = anchor.x * scale, anchor.y * scale
    return Placed(obj, tab, x, y, body.w * scale, body.h * scale, cell_at({}, {}, x, y), layer)


def placed_objects(model: WorkbookModel, size: SlideSize = ONE_TO_ONE) -> tuple[Placed, ...]:
    """Every object of ``model`` on its tab, tab by tab and each bottom first."""
    return tuple(
        placed_object(model, model.get_object(object_id), tab, layer, size)
        for tab in file_tabs(model)
        for layer, object_id in enumerate(model.stack_of(str(tab.id)))
    )


def placed_on_its_sheet(model: WorkbookModel, obj: VisualObject) -> Placed:
    """An object of a sheet of ``model`` placed on that sheet (for a file that is patched, whose tabs are sheets)."""
    assert isinstance(obj.anchor, CellAnchor)  # (a kept file has no slides)
    sheet = model.sheets[obj.anchor.sheet]
    return placed_object(model, obj, FileTab(sheet.id, sheet.name, is_slide=False))
