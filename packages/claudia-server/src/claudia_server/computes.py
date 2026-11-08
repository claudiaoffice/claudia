"""The methods of the spreadsheet app: what a table view needs to show cells and to take what people type (E3.1).

``computes_methods`` is ``core_methods`` plus ``sheets``, ``cells``, ``set_cells``, ``add_sheet``, ``structure``,
``sizes``, ``resize_lines``, ``objects``, ``images``, ``styles``, ``add_image``, ``move_object``,
``resize_object``, ``rotate_object`` and ``remove_object``. Cells
travel as ``[row, column, content]`` with zero-based indexes and the content as a client shows it: ``{"t":
"int"|"float"|"text"|"bool", "v": value}``, and for a formula the value it gave (``t`` may also be ``"error"``,
with the code in ``v``) plus its text under ``"f"``. What people type goes through ``parse_input``, so a client
sends the text of the cell (``=B2*2`` for a formula) and the server decides what it means. Every write may carry
the ``base`` revision of the client's view, as ``apply`` does.

An object is a shared ``ObjectBody`` plus a ``CellAnchor`` (E10.16): the body — kind, size, style, text, shape,
image, rotation, snap — travels the wire identically in all three apps, and only ``anchor`` differs, as
``{"kind": "cell", "container": <sheet>, "row": r, "col": c}``. An image is anchored to a cell and neither the
anchor nor the size ever changes because of ``structure`` or ``resize_lines`` — only ``move_object`` (dragging it
to another cell) moves it, and ``resize_object`` resizes it (E10.11).
"""

from __future__ import annotations

import secrets

from claudia_computes import (
    AddSheet,
    CellAnchor,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    ResizeLines,
    SetCells,
    SheetId,
    Structure,
    WorkbookModel,
    parse_input,
)
from claudia_computes.model import (
    MAX_COL_WIDTH,
    MAX_COLS,
    MAX_ROW_HEIGHT,
    MAX_ROWS,
    MIN_COL_WIDTH,
    MIN_ROW_HEIGHT,
)
from claudia_core import (
    AddObject,
    Batch,
    DefineImage,
    ImageImport,
    MoveObject,
    ObjectBody,
    RemoveObject,
    ResizeObject,
    RotateObject,
    decode_image,
)
from claudia_core.clock import utc_now

from .images import image_bytes
from .protocol import Context, RequestError, core_methods
from .styles import add_style_methods

MAX_WINDOW_CELLS = 50_000  # positions in one ``cells`` window
MAX_TYPED_CELLS = 10_000  # cells in one ``set_cells``
MAX_RESIZED_LINES = 1_000  # lines in one ``resize_lines``
MAX_SHEET_NAME = 60
AXES = {
    ("row", True): InsertRows,
    ("row", False): DeleteRows,
    ("col", True): InsertCols,
    ("col", False): DeleteCols,
}
SIZE_LIMITS = {"row": (MIN_ROW_HEIGHT, MAX_ROW_HEIGHT), "col": (MIN_COL_WIDTH, MAX_COL_WIDTH)}

computes_methods = core_methods.extended()
# ``styles``, ``palette``, ``change_style``, ``rename_style``, ``check_css`` and ``set_object_style`` are the
# same in every app (E1.10, D200). A workbook has no rule of its own about who may change them.
add_style_methods(computes_methods)
computes_methods.kind("image")(image_bytes)


def _workbook(ctx: Context) -> WorkbookModel:
    model = ctx.document.model
    if not isinstance(model, WorkbookModel):
        raise RequestError("command_error", "this document is not a workbook")
    return model


def _index(value, limit: int, what: str):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < limit:
        raise RequestError("bad_request", f"{what} must be a whole number from 0 to {limit - 1}")
    return value


def _fresh_object_id(taken) -> str:
    """An id nobody has used in this document. Ids are random, never counted: the id of a removed object must not
    come back, or undoing its removal would collide with the newcomer (mirrors ``creates.py``'s ``_fresh``)."""
    while True:
        candidate = f"o{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


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


@computes_methods.method("sizes", "sheet:str")
def _sizes(ctx, *, sheet):
    """The rows and columns of a sheet that were given a size away from the default (D135), as
    `{revision, rows: [[row, height]], cols: [[col, width]]}`, each sorted by index. A line not listed shows at the
    sheet's default (`DEFAULT_ROW_HEIGHT`/`DEFAULT_COL_WIDTH` in `claudia_computes.model`)."""
    found = _workbook(ctx).sheet(sheet)
    return {
        "revision": _rev(ctx),
        "rows": [[r, h] for r, h in sorted(found.row_heights.items())],
        "cols": [[c, w] for c, w in sorted(found.col_widths.items())],
    }


def _sized(axis: str, items: list) -> tuple[tuple[int, float | None], ...]:
    if len(items) > MAX_RESIZED_LINES:
        raise RequestError("bad_request", f"resize_lines: at most {MAX_RESIZED_LINES} lines at a time")
    limit = MAX_ROWS if axis == "row" else MAX_COLS
    lo, hi = SIZE_LIMITS[axis]
    sizes = []
    for item in items:
        if not (isinstance(item, list) and len(item) == 2):
            raise RequestError("bad_request", "resize_lines: each line is [index, size]")
        index, size = item
        index = _index(index, limit, "index")
        if size is not None:
            if isinstance(size, bool) or not isinstance(size, (int, float)):
                raise RequestError("bad_request", "resize_lines: size must be a number or null")
            if not lo <= size <= hi:
                raise RequestError("bad_request", f"resize_lines: size must be between {lo} and {hi}")
        sizes.append((index, None if size is None else float(size)))
    return tuple(sizes)


@computes_methods.method("resize_lines", "sheet:str axis:str sizes:list base:revision?", write=True)
def _resize_lines(ctx, *, sheet, axis, sizes, base):
    """Set (or clear, with `null`) the height of rows or the width of columns: `axis` is "row" or "col", `sizes` a
    list of `[index, size]`. One change in the history. Same errors as `apply`."""
    if axis not in SIZE_LIMITS:
        raise RequestError("bad_request", 'resize_lines: axis must be "row" or "col"')
    applied = ctx.document.execute(ResizeLines(sheet, axis, _sized(axis, sizes)), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("objects", "sheet:str")
def _objects(ctx, *, sheet):
    """The floating objects of a sheet, the one in front last, as `{revision, sheet, objects}`. An object is
    `{id, sheet, kind, row, col, w, h, image, imported}`, anchored to the cell at (`row`, `col`) with a pixel
    size that never changes on its own: inserting, deleting or resizing rows/columns never moves or resizes it,
    only `move_object` does. `imported`'s `source_path` is only sent to the person who imported that image
    (everyone else sees `null` there, not the path)."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", f"unknown sheet {sheet!r}")
    objects = [obj.to_data_for(ctx.user) for obj in workbook.objects_on(sheet)]
    return {"revision": _rev(ctx), "sheet": sheet, "objects": objects}


@computes_methods.method("images")
def _images(ctx):
    """The decoded image assets this document has taken in (and what its image objects are drawn with), each as
    `{id, format, width, height, animated, data, first_frame}` (`data`/`first_frame` are base64). There is no
    library to pick from: an image always comes in through `add_image`."""
    workbook = _workbook(ctx)
    return [image.to_data() for _, image in sorted(workbook.images.items())]


@computes_methods.method(
    "add_image",
    "sheet:str row:int col:int w:int h:int data:image alt:str source_name:str source_path:str? base:revision?",
    write=True,
)
def _add_image(ctx, *, sheet, row, col, w, h, data, alt, source_name, source_path, base):
    """Import a picture from disk and anchor it to a cell of a sheet: `data` is the file's bytes, base64. `alt`
    is a short, required description of what it shows. `source_name` is the file name as the client has it;
    `source_path` is its full path if the client could supply one (a plain web browser cannot, for its own
    security — send `null`). Returns the new object's id and the revision. The image keeps its own proportions,
    and its pixel size (and anchor) never change on their own afterwards — only `move_object` moves it."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", f"unknown sheet {sheet!r}")
    asset = decode_image(data)
    steps: list = [] if asset.id in workbook.images else [DefineImage(asset)]
    imported = ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": alt,
            "imported_by": ctx.user,
            "imported_at": utc_now(),
            "source": "disk",
            "source_name": source_name,
            "source_path": source_path,
        }
    )
    object_id = _fresh_object_id(workbook.objects)
    body = ObjectBody(object_id, "image", w, h, "plain-image", image=asset.id, imported=imported)
    steps.append(AddObject(body, CellAnchor(SheetId(sheet), row, col).to_data()))
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Add image")
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"object": object_id, "revision": applied.revision.to_data()}


@computes_methods.method("move_object", "id:str row:int col:int base:revision?", write=True)
def _move_object(ctx, *, id, row, col, base):
    """Move an object so that its anchor is at (`row`, `col`); its pixel size stays."""
    sheet = _workbook(ctx).get_object(id).anchor.sheet
    command = MoveObject(id, CellAnchor(sheet, row, col).to_data())
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("resize_object", "id:str row:int col:int w:int h:int base:revision?", write=True)
def _resize_object(ctx, *, id, row, col, w, h, base):
    """Give an object a new frame: its anchor cell and its pixel size together, since dragging a corner moves the
    corner. An image keeps its own proportions, so `w` and `h` must match them."""
    sheet = _workbook(ctx).get_object(id).anchor.sheet
    command = ResizeObject(id, CellAnchor(sheet, row, col).to_data(), w, h)
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("rotate_object", "id:str rotation:int base:revision?", write=True)
def _rotate_object(ctx, *, id, rotation, base):
    """Turn an object to `rotation` whole degrees clockwise (0 to 359); its frame stays."""
    applied = ctx.document.execute(RotateObject(id, rotation), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("remove_object", "id:str base:revision?", write=True)
def _remove_object(ctx, *, id, base):
    """Take an object off its sheet. Undo brings it back in the same place of the stacking order."""
    applied = ctx.document.execute(RemoveObject(id), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}
