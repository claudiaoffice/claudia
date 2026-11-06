"""The methods of the spreadsheet app: what a table view needs to show cells and to take what people type (E3.1).

``computes_methods`` is ``core_methods`` plus ``sheets``, ``cells``, ``set_cells``, ``add_sheet`` and ``structure``.
Cells travel as ``[row, column, content]`` with zero-based indexes and the content as a client shows it:
``{"t": "int"|"float"|"text"|"bool", "v": value}``, and for a formula the value it gave (``t`` may also be ``"error"``,
with the code in ``v``) plus its text under ``"f"``. What people type goes through ``parse_input``, so a client sends
the text of the cell (``=B2*2`` for a formula) and the server decides what it means. Every write may carry the
``base`` revision of the client's view, as ``apply`` does.
"""

from __future__ import annotations

from claudia_computes import (
    AddSheet,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    SetCells,
    SheetId,
    Structure,
    WorkbookModel,
    parse_input,
)
from claudia_computes.model import MAX_COLS, MAX_ROWS

from .protocol import Context, RequestError, core_methods

MAX_WINDOW_CELLS = 50_000  # positions in one ``cells`` window
MAX_TYPED_CELLS = 10_000  # cells in one ``set_cells``
MAX_SHEET_NAME = 60
AXES = {
    ("row", True): InsertRows,
    ("row", False): DeleteRows,
    ("col", True): InsertCols,
    ("col", False): DeleteCols,
}

computes_methods = core_methods.extended()


def _workbook(ctx: Context) -> WorkbookModel:
    model = ctx.document.model
    if not isinstance(model, WorkbookModel):
        raise RequestError("command_error", "this document is not a workbook")
    return model


def _index(value, limit: int, what: str):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < limit:
        raise RequestError("bad_request", f"{what} must be a whole number from 0 to {limit - 1}")
    return value


@computes_methods.method("sheets")
def _sheets(ctx):
    """The sheets in order, each as `{id, name, rows, cols}`; rows and cols are the extent that holds something."""
    return [
        {"id": sheet.id, "name": sheet.name, **dict(zip(("rows", "cols"), sheet.extent(), strict=True))}
        for sheet in _workbook(ctx).sheets.values()
    ]


@computes_methods.method("cells", "sheet:str row0:int row1:int col0:int col1:int")
def _cells(ctx, *, sheet, row0, row1, col0, col1):
    """The cells that hold something in a window of a sheet (both ends included), sorted by row and column, as
    `{revision, cells: [[row, col, content]]}`; a formula comes with its value and, under `f`, its text. A window has at
    most 50000 positions; ask for what is visible."""
    row0, row1 = _index(row0, MAX_ROWS, "row0"), _index(row1, MAX_ROWS, "row1")
    col0, col1 = _index(col0, MAX_COLS, "col0"), _index(col1, MAX_COLS, "col1")
    if row1 < row0 or col1 < col0:
        raise RequestError("bad_request", "cells: the window must not end before it starts")
    if (row1 - row0 + 1) * (col1 - col0 + 1) > MAX_WINDOW_CELLS:
        raise RequestError("bad_request", f"cells: window too large (at most {MAX_WINDOW_CELLS} positions)")
    found = _workbook(ctx).sheet(sheet)
    inside = found.cells_in(row0, row1, col0, col1)
    return {"revision": _rev(ctx), "cells": [[r, c, found.view((r, c))] for r, c in inside]}


def _rev(ctx) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _typed(ctx, items: list) -> tuple[tuple[int, int, dict | None], ...]:
    if len(items) > MAX_TYPED_CELLS:
        raise RequestError("bad_request", f"set_cells: at most {MAX_TYPED_CELLS} cells at a time")
    cells = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"row", "col", "input"}:
            raise RequestError("bad_request", "set_cells: each cell is an object with row, col and input")
        text = item["input"]
        if not isinstance(text, str) or len(text) > ctx.limits.max_text:
            raise RequestError(
                "bad_request", f"set_cells: input must be text of at most {ctx.limits.max_text} characters"
            )
        cells.append((_index(item["row"], MAX_ROWS, "row"), _index(item["col"], MAX_COLS, "col"), parse_input(text)))
    return tuple(cells)


@computes_methods.method("set_cells", "sheet:str cells:list base:revision?", write=True)
def _set_cells(ctx, sheet, cells, base):
    """Type into cells: `cells` is a list of `{row, col, input}` where `input` is what the person typed (empty clears;
    a leading apostrophe makes text). One change in the history. Same errors as `apply`."""
    applied = ctx.document.execute(SetCells(sheet, _typed(ctx, cells)), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("add_sheet", "name:str base:revision?", write=True)
def _add_sheet(ctx, name, base):
    """Add a sheet at the end. The name must be new (case does not matter) and not empty. Returns the new sheet's id
    and the revision."""
    name = name.strip()
    if not name or len(name) > MAX_SHEET_NAME:
        raise RequestError("bad_request", f"add_sheet: the name must have 1 to {MAX_SHEET_NAME} characters")
    taken = _workbook(ctx).sheets
    number = len(taken) + 1
    while f"s{number}" in taken:
        number += 1
    sheet_id = f"s{number}"
    applied = ctx.document.execute(AddSheet(SheetId(sheet_id), name), author=ctx.user, base=base)
    return {"sheet": sheet_id, "revision": applied.revision.to_data()}


@computes_methods.method("structure", "sheet:str axis:str insert:bool at:int count:int=1 base:revision?", write=True)
def _structure(ctx, *, sheet, axis, insert, at, count, base):
    """Insert or delete `count` rows or columns (`axis` is "row" or "col") at index `at`; cells move with them.
    Colleagues' places in the sheet move too."""
    edit = AXES.get((axis, insert))
    if edit is None:
        raise RequestError("bad_request", 'structure: axis must be "row" or "col"')
    applied = ctx.document.execute(Structure(edit(sheet, at, count)), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}
