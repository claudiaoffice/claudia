"""The methods of the spreadsheet app: what a table view needs to show cells and to take what people type (E3.1).

``computes_methods`` is ``core_methods`` plus ``sheets``, ``cells``, ``set_cells``, ``add_sheet``, ``structure``,
``sizes``, ``resize_lines``, ``objects``, ``images``, ``styles``, ``add_image``, ``move_object``,
``resize_object``, ``rotate_object``, ``remove_object``, ``diagrams``, ``charts``, ``chart_figure``,
``define_diagram``, ``update_diagram``, ``forget_diagram``, ``add_diagram_object``, ``add_chart``,
``remove_chart``, for named ranges, tables and queries (E6.5), ``names``, ``define_name``, ``rename_name``,
``remove_name``, ``sql_preview`` and ``define_sql``, and for search and replace (E6.20) ``search_find``,
``search_preview`` and ``search_replace``. Cells
travel as ``[row, column, content]`` with zero-based indexes and the content as a client shows it: ``{"t":
"int"|"float"|"text"|"bool", "v": value}``, and for a formula the value it gave (``t`` may also be ``"error"``,
with the code in ``v``) plus its text under ``"f"``. What people type goes through ``parse_input``, so a client
sends the text of the cell (``=B2*2`` for a formula) and the server decides what it means. Every write may carry
the ``base`` revision of the client's view, as ``apply`` does.

A *name* (E6.5, D600) is a named range, a table (a name whose first row is a header) or the result of a ``SQL()``
cell, as ``{name, scope, kind, header, grows, purpose, column_purposes, sheet, region, a1, anchor, columns, rows}``:
``scope`` is a sheet id or ``null`` (the whole workbook), ``kind`` is ``"range"`` or ``"result"``, ``region`` is
``{sheet, row0, col0, row1, col1}`` (header row included; ``null`` for a result that has none), ``columns`` is
``[{name, type, purpose}]`` with the names as a query sees them. A cell that shows a part of a query result comes
with ``"spill": true`` and ``"from": [row, col]`` (the formula that fills it): it is not stored and cannot be typed
into (``set_cells`` refuses it with ``command_error``).

An object is a shared ``ObjectBody`` plus a ``CellAnchor`` (E10.16): the body — kind, size, style, text, shape,
image, rotation, snap — travels the wire identically in all three apps, and only ``anchor`` differs, as
``{"kind": "cell", "container": <sheet>, "row": r, "col": c}``. An image is anchored to a cell and neither the
anchor nor the size ever changes because of ``structure`` or ``resize_lines`` — only ``move_object`` (dragging it
to another cell) moves it, and ``resize_object`` resizes it (E6.17).

A chart (E6.6) is a :class:`~claudia_computes.ChartSpec` *definition* — a cell range plus how to read it and its
titles — shown as a floating ``"diagram"`` object (``add_diagram_object``), a tab (``add_chart``), or both from
the very same definition, exactly as two image objects may share one image asset. ``define_diagram`` takes a
definition into the document and hands back the id it was given (the server assigns it, the way ``add_sheet``
assigns a sheet id, rather than the client making one up); ``chart_figure`` turns a definition plus its sheet's
*live* cells into the Plotly figure (``{"data": [...], "layout": {...}}``) both clients draw unchanged — a
client asks for it again after any ``cells`` push event whose ``sheet``/``positions`` could touch the chart's
own range; move/resize/rotate/remove already work on a diagram object with no code of their own (E10.16's
generic object commands do not care what kind an object is).
"""

from __future__ import annotations

import secrets
import time
from collections import Counter

from claudia_computes_io import (
    Untranslatable,
    ods_export_losses,
    workbook_to_ods,
    workbook_to_xlsx,
    xlsx_export_losses,
)
from claudia_computes_io.extensions import to_excel

from claudia_computes import (
    CELL_SLOTS,
    AddChart,
    AddSheet,
    CellAnchor,
    DefineName,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    NamedRange,
    RemoveChart,
    RemoveName,
    RenameName,
    Resample,
    ResizeLines,
    SetCells,
    SetCellStyle,
    SetRandomSeed,
    SheetId,
    Structure,
    WorkbookModel,
    get_function,
    parse_input,
    search_functions,
)
from claudia_computes.cellstyles import check_area
from claudia_computes.distributions import DISTRIBUTIONS, check_parameters, quantile
from claudia_computes.model import (
    MAX_COL_WIDTH,
    MAX_COLS,
    MAX_ROW_HEIGHT,
    MAX_ROWS,
    MIN_COL_WIDTH,
    MIN_ROW_HEIGHT,
)
from claudia_computes.names import PURPOSES  # noqa: F401
from claudia_computes.refs import CellRef, RangeRef
from claudia_computes.region import CellRegion
from claudia_computes.search import (
    EXTRA_PARTS,
    KINDS,
    Plan,
    plan_replacement,
    replace_command,
    scan,
)
from claudia_computes.trace import REACHES
from claudia_computes.values import FormulaError
from claudia_core import (
    AddObject,
    Batch,
    Command,
    CompiledSearch,
    DefineDiagram,
    DefineImage,
    ForgetDiagram,
    ImageImport,
    MoveObject,
    ObjectBody,
    Query,
    RemoveObject,
    ResizeObject,
    RotateObject,
    SearchError,
    UpdateDiagram,
    decode_image,
)
from claudia_core.clock import utc_now

from .images import image_bytes
from .office_export import document_info, office_export
from .protocol import Context, RequestError, core_methods
from .style_targets import OBJECTS
from .styles import add_style_methods

MAX_WINDOW_CELLS = 50_000  # positions in one ``cells`` window
MAX_TYPED_CELLS = 10_000  # cells in one ``set_cells``
MAX_RESIZED_LINES = 1_000  # lines in one ``resize_lines``
MAX_SHEET_NAME = 60
SEARCH_SECONDS = 2.0  # how long one search may look (the worker pool's budget, D284); then it says it stopped
MAX_REPLACED_CELLS = 10_000  # cells one replacement may change, as many as one ``set_cells``
MAX_PREVIEWED = 2_000  # changes a preview lists (it says how many there are in all)
AXES = {
    ("row", True): InsertRows,
    ("row", False): DeleteRows,
    ("col", True): InsertCols,
    ("col", False): DeleteCols,
}
SIZE_LIMITS = {"row": (MIN_ROW_HEIGHT, MAX_ROW_HEIGHT), "col": (MIN_COL_WIDTH, MAX_COL_WIDTH)}


class _CellTargets:
    """Cells as a style target, ``{"sheet": id, "range": [r0, c0, r1, c1]}`` (E6.13, D307, D311): the two slots of a
    cell, through the shared ``apply_style`` and ``deviate`` (:mod:`claudia_server.style_targets`). A whole sheet,
    whole columns or whole rows are ranges of the sheet's own size, and go into the layer of their shape."""

    key = "sheet"

    def thing(self, model: WorkbookModel, target: dict) -> str:
        sheet = target.get("sheet")
        if not isinstance(sheet, str):
            raise ValueError("a target names its sheet by id")
        check_area(target.get("range"))
        if SheetId(sheet) not in model.sheets:
            raise KeyError(f"no sheet {sheet!r}")
        return "cell"

    def style_in(self, model: WorkbookModel, target: dict, slot: str) -> str | None:
        # The style of the range's first cell: what the menu shows for a selection is its anchor cell's.
        r0, c0, _, _ = target["range"]
        return model.sheet(SheetId(target["sheet"])).cell_styles.style_at(r0, c0, slot)[0]

    def command(self, model: WorkbookModel, target: dict, slot: str, style: str) -> Command:
        return SetCellStyle.applying(model, SheetId(target["sheet"]), slot, check_area(target["range"]), style)

    def uses(self, model: WorkbookModel) -> Counter[str]:
        counted: Counter[str] = Counter()
        for sheet in model.sheets.values():
            counted.update(sheet.cell_styles.uses())
        return counted


computes_methods = core_methods.extended()
# ``styles``, ``palette``, ``change_style``, ``rename_style``, ``check_css``, ``set_object_style`` and the one style
# API (``apply_style``, ``deviate``) are the same in every app (E1.10, D200); a workbook's targets are its floating
# objects and its cells. A workbook has no rule of its own about who may change them.
add_style_methods(computes_methods, targets=(OBJECTS, _CellTargets()))
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


def _fresh_diagram_id(taken) -> str:
    """As :func:`_fresh_object_id`, for a diagram definition. The client never makes up this id itself — unlike
    an image, whose asset id is a content hash, two otherwise-identical chart definitions are still two
    definitions, so the server assigns a fresh one every time, the way ``add_sheet`` assigns a sheet id."""
    while True:
        candidate = f"g{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


def _fresh_chart_id(taken) -> str:
    """As :func:`_fresh_object_id`, for a chart tab."""
    while True:
        candidate = f"t{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


def _diagram_definition(workbook: WorkbookModel, diagram_id: str, what: str) -> None:
    if diagram_id not in workbook.diagrams:
        raise RequestError("command_error", f"{what}: this document does not know the diagram {diagram_id!r}")


@computes_methods.method("sheets")
def _sheets(ctx):
    """The sheets in order, each as `{id, name, rows, cols}`; rows and cols are the extent that holds something."""
    return [
        {"id": sheet.id, "name": sheet.name, **dict(zip(("rows", "cols"), sheet.extent(), strict=True))}
        for sheet in _workbook(ctx).sheets.values()
    ]


@computes_methods.method("export_office", "format:str")
def _export_office(ctx, *, format):
    """The document's current content as bytes of an Excel file (`format` `"xlsx"`) or an OpenDocument
    spreadsheet (`"ods"`), wrapped for the wire as `{format, content_type, data}` (`data` base64); the answer
    also has `losses`, what the file could not hold, as `{kind, detail, count}` codes: for both formats since
    E6.22 (a draw Excel has no formula for, `formula`/`random`; alternatives, `alternatives`). No tracked changes, no
    history, no chat — just the workbook as it stands now (D212); an ods says in its metadata when the workbook was
    made and last changed, and by whom, read from the log (D411), and holds every formula with the value it shows
    (D413)."""
    if format not in ("xlsx", "ods"):
        raise RequestError("bad_request", 'export_office: format must be "xlsx" or "ods"')
    book = _workbook(ctx)
    if format == "xlsx":
        return office_export(format, workbook_to_xlsx(book), xlsx_export_losses(book))
    info = document_info(ctx.document.log, ctx.document.branch)
    return office_export(format, workbook_to_ods(book, info=info), ods_export_losses(book))


MAX_RESAMPLE = 1_000  # draws one ``resample`` may skip
MAX_SEED = 2**53  # a seed a JSON number holds exactly


def _whole(value, low: int, high: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RequestError("bad_request", f"{what} must be a whole number from {low} to {high}")
    return value


@computes_methods.method("random_state")
def _random_state(ctx):
    """What every random number in the workbook is a function of (E6.22, D291): `{revision, seed, draw}`. All
    users see the same numbers because they share both."""
    book = _workbook(ctx)
    return {"revision": _rev(ctx), "seed": book.random_seed, "draw": book.random_draw}


@computes_methods.method("resample", "steps:int=1 base:revision?", write=True)
def _resample(ctx, *, steps, base):
    """Draw fresh random numbers for everyone (Tools > Resample, F9): the draw number goes up by `steps` (1 to
    1000). Relative, so resampling by two people at once counts both, and one undo step. Returns the revision and
    the new `draw`."""
    steps = _whole(steps, 1, MAX_RESAMPLE, "resample: steps")
    applied = ctx.document.execute(Resample(steps), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), "draw": _workbook(ctx).random_draw}


@computes_methods.method("set_random_seed", "seed:int base:revision?", write=True)
def _set_random_seed(ctx, *, seed, base):
    """Give the workbook's random numbers a seed (0 to 2^53): the same seed and draw number give the same numbers
    on every computer, so a model can be reproduced. One undo step."""
    seed = _whole(seed, 0, MAX_SEED, "set_random_seed: seed")
    applied = ctx.document.execute(SetRandomSeed(seed), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


MAX_PREVIEW_DRAWS = 1_000  # draws in one ``random_preview``


def _number_text(value: float) -> str:
    """A number as a formula writes it: ``1000`` and not ``1000.0``."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _limit(value, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError("bad_request", f"random_preview: {what} must be a number or null")
    return value


@computes_methods.method("random_preview", "distribution:str params:list low:number? high:number? draws:int=200")
def _random_preview(ctx, *, distribution, params, low, high, draws):
    """What a distribution would give, for the Random generator (E6.22): `{formula, excel, continuous, draws}`.
    `params` are the numbers after the distribution's name (`discrete`: value, weight, value, weight…), `low` and
    `high` cut a continuous one. `formula` is what to type, `excel` what a file would hold instead (null when Excel
    has no formula for it and the file gets the value, D292), `draws` the distribution's own quantiles at `draws`
    evenly spread points (1 to 1000), sorted: the same function every `RANDOM` uses, so the preview is not an
    approximation. Nothing in the document is read or changed."""
    draws = _whole(draws, 1, MAX_PREVIEW_DRAWS, "random_preview: draws")
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) for p in params):
        raise RequestError("bad_request", "random_preview: params must be numbers")
    low, high = _limit(low, "low"), _limit(high, "high")
    known = DISTRIBUTIONS.get(distribution.casefold()) if isinstance(distribution, str) else None
    if known is None:
        raise RequestError("bad_request", f"random_preview: there is no distribution {distribution!r}")
    try:
        check_parameters(known, params)
        points = [quantile(known.name, (i + 0.5) / draws, params, low=low, high=high) for i in range(draws)]
    except FormulaError as exc:
        raise RequestError("command_error", f"random_preview: {exc.detail or exc.code}") from None
    arguments = [_number_text(p) for p in params]
    if low is not None or high is not None:
        arguments += ["" if low is None else _number_text(low), "" if high is None else _number_text(high)]
    formula = f'=RANDOM("{known.name}",{",".join(arguments)})'
    try:
        excel = to_excel(formula)
    except Untranslatable:
        excel = None
    return {"formula": formula, "excel": excel, "continuous": known.continuous, "draws": points}


@computes_methods.method("outcome_table", 'sheet:str row:int col:int combine:str="all"')
def _outcome_table(ctx, *, sheet, row, col, combine):
    """Every outcome of a cell that depends on alternatives (`{a, b, c}` in input cells), as `{revision, table}`:
    the alternatives that make each outcome (`inputs`, `rows` with their `choice`), the `sensitivity` of the
    outcome to each input, and whether the outcomes were `sampled` (very many combinations). `combine` is `"all"`
    (every combination) or `"pair"` (the first alternatives together, the second ones, ...; command_error when the
    inputs have different numbers of alternatives). `table` is null for a cell that depends on none."""
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    if combine not in ("all", "pair"):
        raise RequestError("bad_request", 'outcome_table: combine must be "all" or "pair"')
    try:
        table = _workbook(ctx).outcome_table(SheetId(sheet), row, col, combine=combine)
    except (KeyError, ValueError) as exc:
        raise RequestError("command_error", str(exc)) from None
    return {"revision": _rev(ctx), "table": None if table is None else table.to_data()}


@computes_methods.method("trace", 'sheet:str row:int col:int reach:str="group" window:list?')
def _trace(ctx, *, sheet, row, col, reach, window):
    """Follow a computation (E6.23): the cells that take part in one with this cell, as `{revision, trace}` where
    `trace.cells` is `[[row, col, role]]` with `role` `input`, `calc` or `output`, `other` counts the connected
    cells on other sheets per sheet, and `connected` says whether the cell is part of a computation at all.
    `reach` is `"group"` (everything connected) or `"chain"` (only what the cell feeds and is fed by); `window`
    is `[row0, col0, row1, col1]`, the cells a client shows, to which the listed cells are cut (at most 50000
    positions). Nothing is changed: lighting up cells is a view, not an edit."""
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    if reach not in REACHES:
        raise RequestError("bad_request", f"trace: reach must be one of {', '.join(REACHES)}")
    area = None
    if window is not None:
        if not isinstance(window, list) or len(window) != 4:
            raise RequestError("bad_request", "trace: window is [row0, col0, row1, col1]")
        r0, c0 = _index(window[0], MAX_ROWS, "window row0"), _index(window[1], MAX_COLS, "window col0")
        r1, c1 = _index(window[2], MAX_ROWS, "window row1"), _index(window[3], MAX_COLS, "window col1")
        if r1 < r0 or c1 < c0:
            raise RequestError("bad_request", "trace: the window must not end before it starts")
        if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_WINDOW_CELLS:
            raise RequestError("bad_request", f"trace: window too large (at most {MAX_WINDOW_CELLS} positions)")
        area = (r0, c0, r1, c1)
    try:
        found = _workbook(ctx).trace(SheetId(sheet), row, col, reach=reach, window=area)
    except KeyError as exc:
        raise RequestError("command_error", str(exc)) from None
    return {"revision": _rev(ctx), "trace": found.to_data()}


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


@computes_methods.method("cell_styles", "sheet:str row0:int row1:int col0:int col1:int")
def _cell_styles(ctx, *, sheet, row0, row1, col0, col1):
    """The style ranges that meet a window of a sheet, cut to it (E6.13, D307): `{revision, ranges: [{slot, layer,
    area, style}]}`, least specific layer first, so a client paints them in order and a later one wins. `slot` is
    `box` or `words`, `layer` is `sheet`, `column`, `row` or `range`, `area` is `[r0, c0, r1, c1]`. A cell no range
    covers has `body-text` (D313). Unlike `cells`, the window may be as large as the sheet: a range is one entry
    however many cells it covers."""
    row0, row1 = _index(row0, MAX_ROWS, "row0"), _index(row1, MAX_ROWS, "row1")
    col0, col1 = _index(col0, MAX_COLS, "col0"), _index(col1, MAX_COLS, "col1")
    if row1 < row0 or col1 < col0:
        raise RequestError("bad_request", "cell_styles: the window must not end before it starts")
    found = _workbook(ctx).sheet(sheet)
    return {"revision": _rev(ctx), "ranges": found.cell_styles.ranges_in((row0, col0, row1, col1))}


@computes_methods.method("clear_cell_style", "sheet:str range:list slot:str? base:revision?", write=True)
def _clear_cell_style(ctx, *, sheet, range, slot, base):
    """“Clear cell style” (D317): take the style of `range` away — in one slot, or in both — so that what lies
    beneath shows through: the row's, the column's or the sheet's style, or Body text. One undo step."""
    try:
        area = check_area(range)
        slots = CELL_SLOTS if slot is None else (slot,)
        if slot is not None and slot not in CELL_SLOTS:
            raise ValueError(f"a cell has no slot “{slot}”; it has {', '.join(CELL_SLOTS)}")
        model = _workbook(ctx)
        steps = [SetCellStyle.applying(model, SheetId(sheet), one, area, None) for one in slots]
    except (KeyError, ValueError) as exc:
        raise RequestError("command_error", str(exc)) from None
    try:
        applied = ctx.document.execute(Batch(tuple(steps), "Clear cell style"), author=ctx.user, base=base)
    except ValueError as exc:
        raise RequestError("command_error", str(exc)) from None
    return {"revision": applied.revision.to_data()}


@computes_methods.method("cell_style_at", "sheet:str row:int col:int")
def _cell_style_at(ctx, *, sheet, row, col):
    """Where a cell's look comes from: `{box: {style, layer}, words: {style, layer}}`, the layer being `range`,
    `row`, `column`, `sheet` or `default` (no range covers it) — what the style menu says about a cell (D307)."""
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    styles = _workbook(ctx).sheet(sheet).cell_styles
    return {slot: dict(zip(("style", "layer"), styles.style_at(row, col, slot), strict=True)) for slot in CELL_SLOTS}


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


@computes_methods.method("diagrams")
def _diagrams(ctx):
    """The chart definitions this document knows (E6.6), each as `{format, id, kind, range, series_in, title,
    x_title, y_title, legend, gridlines}` — a chart that reads a named table or result has `source` and
    `source_scope` (a sheet id, or null for a workbook-wide name) where `range` would be (E6.5) — what a chart
    tab or a floating diagram object may show. `range` is `{first, last}`, each a cell reference naming its own
    sheet; a definition is not itself placed anywhere."""
    return [spec.to_data() for spec in _workbook(ctx).diagrams.values()]


@computes_methods.method("charts")
def _charts(ctx):
    """The chart tabs, in tab order, each as `{id, name, spec_id}`. `spec_id` names one of `diagrams`; two tabs
    (or a tab and a floating diagram object) may share the very same definition."""
    return [chart.to_data() for chart in _workbook(ctx).charts.values()]


@computes_methods.method("chart_figure", "diagram:str")
def _chart_figure(ctx, *, diagram):
    """A diagram's Plotly figure, read live off the sheet its range names, as `{revision, figure}` — the same
    `figure` for every client, computed once here rather than twice (`e0-3-web-surface-notes.md`). Ask again
    after any `cells` push event whose `sheet`/`positions` might overlap the diagram's own range; this server
    does not push a fresh figure on its own, since working out which charts are even open to a given client is
    the client's business, not this document's."""
    workbook = _workbook(ctx)
    _diagram_definition(workbook, diagram, "chart_figure")
    return {"revision": _rev(ctx), "figure": workbook.chart_figure(diagram)}


@computes_methods.method("define_diagram", "definition:dict base:revision?", write=True)
def _define_diagram(ctx, *, definition, base):
    """Take a new chart definition into the document: `definition` is `{kind, range, series_in, title, x_title,
    y_title, legend, gridlines}` (E6.6); give `source` (and `source_scope`) instead of `range` to draw a named
    table or `SQL()` result that the chart then follows as it grows or moves (E6.5) — the id and format are this
    server's to assign, not the client's, so neither is sent. Returns the new definition's id and the revision;
    show it with `add_diagram_object`, `add_chart`, or both."""
    if "id" in definition or "format" in definition:
        raise RequestError("bad_request", "define_diagram: id and format are assigned by the server")
    workbook = _workbook(ctx)
    diagram_id = _fresh_diagram_id(workbook.diagrams)
    command = DefineDiagram({**definition, "id": diagram_id, "format": 1})
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"diagram": diagram_id, "revision": applied.revision.to_data()}


@computes_methods.method("update_diagram", "id:str definition:dict base:revision?", write=True)
def _update_diagram(ctx, *, id, definition, base):
    """Redefine a chart in place (E6.6): what a tab or floating object already showing `id` updates to, with
    nothing to re-place. Same shape as `define_diagram`'s `definition`; the id and format are unchanged."""
    _diagram_definition(_workbook(ctx), id, "update_diagram")
    command = UpdateDiagram(id, {**definition, "id": id, "format": 1})
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("forget_diagram", "id:str base:revision?", write=True)
def _forget_diagram(ctx, *, id, base):
    """Let a chart definition go. Refused while a tab or a floating object still shows it — remove or repoint
    those first (`remove_chart`, `remove_object`, or `update_diagram`/`add_chart` onto another definition)."""
    applied = ctx.document.execute(ForgetDiagram(id), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method(
    "add_diagram_object", "sheet:str row:int col:int w:int h:int diagram:str base:revision?", write=True
)
def _add_diagram_object(ctx, *, sheet, row, col, w, h, diagram, base):
    """Put a chart on a sheet as a floating object, showing the definition `diagram` already names
    (`define_diagram`). Returns the new object's id and the revision; `move_object`/`resize_object`/
    `rotate_object`/`remove_object` then work on it exactly as they do on any other object."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", f"unknown sheet {sheet!r}")
    _diagram_definition(workbook, diagram, "add_diagram_object")
    object_id = _fresh_object_id(workbook.objects)
    body = ObjectBody(object_id, "diagram", w, h, "plain-image", diagram=diagram)
    command = AddObject(body, CellAnchor(SheetId(sheet), row, col).to_data())
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"object": object_id, "revision": applied.revision.to_data()}


@computes_methods.method("add_chart", "name:str spec_id:str index:int? base:revision?", write=True)
def _add_chart(ctx, *, name, spec_id, index, base):
    """Add a chart tab showing the definition `spec_id` already names (`define_diagram`); `index` is where in
    the tab order (the end, if omitted). Returns the new tab's id and the revision."""
    name = name.strip()
    if not name or len(name) > MAX_SHEET_NAME:
        raise RequestError("bad_request", f"add_chart: the name must have 1 to {MAX_SHEET_NAME} characters")
    workbook = _workbook(ctx)
    _diagram_definition(workbook, spec_id, "add_chart")
    chart_id = _fresh_chart_id(workbook.charts)
    applied = ctx.document.execute(AddChart(chart_id, name, spec_id, index), author=ctx.user, base=base)
    return {"chart": chart_id, "revision": applied.revision.to_data()}


@computes_methods.method("remove_chart", "id:str base:revision?", write=True)
def _remove_chart(ctx, *, id, base):
    """Remove a chart tab. The definition it showed is untouched — it may still be shown elsewhere
    (`forget_diagram` is the separate, explicit step for letting the definition itself go)."""
    applied = ctx.document.execute(RemoveChart(id), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


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


def _function_summary(entry) -> dict:
    return {"name": entry.name, "signature": entry.signature, "tooltip": entry.tooltip}


@computes_methods.method("functions", 'query:str=""')
def _functions(ctx, *, query):
    """Every cell function whose name or description mentions `query` (case-insensitive), closest name match
    first; every function, alphabetically, if `query` is blank (E13.5/E13.6: the searchable function list). Each
    result is `{name, signature, tooltip}`; fetch the full help text with `function_help`."""
    return [_function_summary(entry) for entry in search_functions(query)]


@computes_methods.method("function_help", "name:str")
def _function_help(ctx, *, name):
    """One function's full help text, by the name a `functions` result gave (while typing, the formula bar asks
    for this itself: E13.5's "in context" is the signature and a short example shown as you type)."""
    entry = get_function(name)
    if entry is None:
        raise RequestError("command_error", f"no function named {name!r}")
    return {"name": entry.name, "signature": entry.signature, "tooltip": entry.tooltip, "help": entry.help}


# ------------------------------------------------------------------------------------ names, tables, queries (E6.5)
MAX_PREVIEW_ROWS = 50


def _scope_of(workbook: WorkbookModel, value, what: str) -> SheetId | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in workbook.sheets:
        raise RequestError("bad_request", f"{what}: scope must be a sheet id or null")
    return SheetId(value)


def _cell_range(workbook: WorkbookModel, data, what: str) -> RangeRef:
    if not isinstance(data, dict) or set(data) != {"sheet", "row0", "col0", "row1", "col1"}:
        raise RequestError("bad_request", f"{what}: range is {{sheet, row0, col0, row1, col1}}")
    sheet = data["sheet"]
    if sheet not in workbook.sheets:
        raise RequestError("bad_request", f"{what}: this document does not know the sheet {sheet!r}")
    r0, c0 = _index(data["row0"], MAX_ROWS, "row0"), _index(data["col0"], MAX_COLS, "col0")
    r1, c1 = _index(data["row1"], MAX_ROWS, "row1"), _index(data["col1"], MAX_COLS, "col1")
    if r1 < r0 or c1 < c0:
        raise RequestError("bad_request", f"{what}: the range must not end before it starts")
    return RangeRef(CellRef(r0, c0, SheetId(sheet)), CellRef(r1, c1, SheetId(sheet)))


def _anchor_of(workbook: WorkbookModel, data, what: str) -> tuple[SheetId, int, int]:
    if not isinstance(data, dict) or set(data) != {"sheet", "row", "col"} or data["sheet"] not in workbook.sheets:
        raise RequestError("bad_request", f"{what}: anchor is {{sheet, row, col}} on a sheet of this document")
    return SheetId(data["sheet"]), _index(data["row"], MAX_ROWS, "row"), _index(data["col"], MAX_COLS, "col")


def _name_from(workbook: WorkbookModel, definition: dict, what: str) -> NamedRange:
    """A :class:`NamedRange` from what a client sends; ``bad_request`` for anything that is not one."""
    allowed = {"name", "scope", "range", "anchor", "header", "grows", "purpose", "column_purposes"}
    if not isinstance(definition, dict) or not set(definition) <= allowed or "name" not in definition:
        raise RequestError("bad_request", f"{what}: the definition is an object with {sorted(allowed)}")
    anchor, given = definition.get("anchor"), definition.get("range")
    if (given is None) == (anchor is None):
        raise RequestError("bad_request", f"{what}: give a range or an anchor (the cell of a SQL() formula), not both")
    try:
        return NamedRange(
            str(definition["name"]),
            _scope_of(workbook, definition.get("scope"), what),
            None if given is None else _cell_range(workbook, given, what),
            bool(definition.get("header", anchor is not None)),
            bool(definition.get("grows", False)),
            definition.get("purpose", "data" if anchor is None else "result"),
            tuple((int(offset), purpose) for offset, purpose in definition.get("column_purposes", ())),
            None if anchor is None else _anchor_of(workbook, anchor, what),
        )
    except (ValueError, TypeError) as problem:
        raise RequestError("bad_request", f"{what}: {problem}") from None


def _name_data(workbook: WorkbookModel, named: NamedRange) -> dict:
    """One name as a client is sent it (see the module documentation)."""
    region = workbook.region_of(named)
    has_header = named.header or named.is_result
    shown = None
    if region is not None:
        sheet_id, r0, c0, r1, c1 = region
        shown = {"sheet": sheet_id, "row0": r0, "col0": c0, "row1": r1, "col1": c1}
        a1 = RangeRef(CellRef(r0, c0, sheet_id), CellRef(r1, c1, sheet_id)).to_a1(workbook.sheet_name_of)
    return {
        "name": named.name,
        "scope": named.scope,
        "kind": "result" if named.is_result else "range",
        "header": has_header,
        "grows": named.grows,
        "purpose": named.purpose,
        "column_purposes": [[offset, purpose] for offset, purpose in named.column_purposes],
        "sheet": named.sheet,
        "sheet_name": workbook.sheet(named.sheet).name,
        "region": shown,
        "a1": None if region is None else a1,
        "anchor": None
        if named.anchor is None
        else {"sheet": named.anchor[0], "row": named.anchor[1], "col": named.anchor[2]},
        "columns": [
            {"name": text, "type": kind, "purpose": named.purpose_of(offset)}
            for offset, (text, kind) in enumerate(workbook.columns_of(named))
        ],
        "rows": 0 if region is None else region[3] - region[1] + (0 if has_header else 1),
    }


@computes_methods.method("names")
def _names(ctx):
    """Every name of the workbook (named ranges, tables and query results), workbook-wide ones first, as
    `{revision, names: [{name, scope, kind, header, grows, purpose, column_purposes, sheet, sheet_name, region, a1,
    anchor, columns, rows}]}`. `columns` are the columns as a query names them, with their type (`int`, `real`,
    `text` or `mixed`) and purpose; `rows` the data rows. Ask again after a `names` push event."""
    workbook = _workbook(ctx)
    return {"revision": _rev(ctx), "names": [_name_data(workbook, named) for named in workbook.names.sorted()]}


@computes_methods.method("define_name", "definition:dict base:revision?", write=True)
def _define_name(ctx, *, definition, base):
    """Give cells a name, or point an existing name (same scope, any case) somewhere else. `definition` is `{name,
    scope?, range, header?, grows?, purpose?, column_purposes?}` with `range` as `{sheet, row0, col0, row1, col1}`
    (header row included), or `anchor` as `{sheet, row, col}` in place of `range` for the result of a `SQL()` cell.
    `purpose` is `input`, `data`, `calc` or `result`; `column_purposes` is `[[offset, purpose]]`. A name is a word
    that is not a cell address. One change in the history."""
    named = _name_from(_workbook(ctx), definition, "define_name")
    applied = ctx.document.execute(DefineName(named), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("rename_name", "old:str new:str scope:str? base:revision?", write=True)
def _rename_name(ctx, *, old, new, scope, base):
    """Call a name something else; the formulas that use it are rewritten. `scope` is the sheet id the name is
    scoped to, or null for a workbook-wide one."""
    scope_id = _scope_of(_workbook(ctx), scope, "rename_name")
    applied = ctx.document.execute(RenameName(scope_id, old, new), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("remove_name", "name:str scope:str? base:revision?", write=True)
def _remove_name(ctx, *, name, scope, base):
    """Take a name away. The cells stay; formulas that used the name show `#NAME?`."""
    scope_id = _scope_of(_workbook(ctx), scope, "remove_name")
    applied = ctx.document.execute(RemoveName(scope_id, name), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@computes_methods.method("sql_preview", "query:str sheet:str limit:int=20")
def _sql_preview(ctx, *, query, sheet, limit):
    """Run a query as a `SQL()` cell on `sheet` would, without changing the document: `{ok: true, columns, rows,
    row_count, ms}` with at most `limit` rows, or `{ok: false, error: {code, detail}}` — the same `#SQL!` a cell would
    show. The same limits apply as in a cell (read only, one second, 100000 rows)."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", f"unknown sheet {sheet!r}")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= MAX_PREVIEW_ROWS:
        raise RequestError("bad_request", f"sql_preview: limit must be a whole number from 0 to {MAX_PREVIEW_ROWS}")
    started = time.perf_counter()
    try:
        table = workbook.query(query, SheetId(sheet))
    except FormulaError as problem:
        return {"ok": False, "error": {"code": problem.code, "detail": problem.detail}}
    return {
        "ok": True,
        "columns": list(table.columns),
        "rows": [list(row) for row in table.rows[:limit]],
        "row_count": len(table.rows),
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


@computes_methods.method("define_sql", "sheet:str row:int col:int query:str name:str? base:revision?", write=True)
def _define_sql(ctx, *, sheet, row, col, query, name, base):
    """Put a query into the cell (`row`, `col`) of `sheet` as `=SQL("...")` and, with `name`, make its result a table
    of that name (workbook-wide), as one change in the history: what the SQL editor's Apply does. A name this cell's
    result already had is replaced."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", f"unknown sheet {sheet!r}")
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    if not isinstance(query, str) or not query.strip() or len(query) > ctx.limits.max_text:
        raise RequestError("bad_request", f"define_sql: query must be text of at most {ctx.limits.max_text} characters")
    formula = '=SQL("' + query.replace('"', '""') + '")'
    steps: list = [SetCells(SheetId(sheet), ((row, col, parse_input(formula)),))]
    anchor = (SheetId(sheet), row, col)
    steps.extend(
        RemoveName(old.scope, old.name)
        for old in workbook.names
        if old.anchor == anchor and (name is None or old.name.casefold() != name.casefold())
    )
    if name is not None:
        try:
            steps.append(DefineName(NamedRange(name, None, None, True, False, "result", (), anchor)))
        except ValueError as problem:
            raise RequestError("bad_request", f"define_sql: {problem}") from None
    applied = ctx.document.execute(steps[0] if len(steps) == 1 else Batch(tuple(steps)), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


# -------------------------------------------------------------------- search and replace (E6.20, D284-D286)
def _search_of(raw: dict) -> CompiledSearch:
    """The compiled search of a query as a client sends it, with computes' own parts; ``SearchError`` if not."""
    return Query.from_data(raw).compile(EXTRA_PARTS)


def _kinds_of(kinds: list | None, method: str) -> tuple[str, ...]:
    chosen = ["text"] if kinds is None else kinds
    if not chosen or not all(isinstance(k, str) and k in KINDS for k in chosen):
        raise RequestError("bad_request", f"{method}: kinds is a list of {', '.join(KINDS)}")
    return tuple(k for k in KINDS if k in chosen)


def _search_scope(ctx, scope: dict | None, method: str) -> tuple[list[str] | None, tuple[int, int, int, int] | None]:
    """``(sheets, area)``: no scope is every sheet, ``{"sheet": id}`` one sheet, and with ``"range": [r0, c0, r1, c1]``
    a selection on it."""
    scope = scope or {}
    if set(scope) - {"sheet", "range"}:
        raise RequestError("bad_request", f"{method}: a scope has a sheet and, on it, a range")
    sheet, area = scope.get("sheet"), scope.get("range")
    if area is not None and sheet is None:
        raise RequestError("bad_request", f"{method}: a range is on a sheet: say which")
    if sheet is None:
        return None, None
    if not isinstance(sheet, str):
        raise RequestError("bad_request", f"{method}: a sheet is named by its id")
    _workbook(ctx).sheet(SheetId(sheet))  # (command_error for a sheet this document does not have)
    if area is None:
        return [sheet], None
    ok = isinstance(area, list) and len(area) == 4 and all(isinstance(n, int) and not isinstance(n, bool) for n in area)
    if not ok or not (0 <= area[0] <= area[2] < MAX_ROWS and 0 <= area[1] <= area[3] < MAX_COLS):
        raise RequestError("bad_request", f"{method}: a range is [first row, first column, last row, last column]")
    return [sheet], (area[0], area[1], area[2], area[3])


def _no_search(error: SearchError, more: dict | None = None) -> dict:
    """What a search that cannot run answers: the mistake, with where it is, and nothing found."""
    return {
        "error": {"message": error.message, "field": error.field, "position": error.position},
        "matches": [],
        "left_out": [],
        "counts": dict.fromkeys(KINDS, 0),
        "total": 0,
        "truncated": False,
        "timed_out": False,
        **(more or {}),
    }


@computes_methods.method("search_find", "query:dict kinds:list? scope:dict?")
def _search_find(ctx, *, query, kinds, scope):
    """Search and replace, the looking (E6.20). `query` is what a person described: `{mode: "text", text}` (what
    is typed is what is found), `{mode: "builder", parts, conditions, combine}` or `{mode: "pattern", find, filter}`
    (her own pattern); each may carry `match_case`, and the first two `whole` (`none`, `entire` or `word`) and, to
    show what a replacement would do, `replace`. A part is `{what, ...}`: `text`, `any_of`, `none_of`, `letter`,
    `digit`, `space`, `any`, `number`, `start`, `end` or, in a workbook, `cellref`. `kinds` is any of `text`,
    `formulas` and `values` (default `["text"]`): the text people typed, formulas as typed, and what cells show
    that was not typed as text. `scope` is `{}` (every sheet), `{sheet}` or `{sheet, range: [r0, c0, r1, c1]}`.

    Answers `{revision, matches, left_out, counts, total, truncated, timed_out, pattern}`. A match is `{sheet, row,
    col, kind, number, start, end, parts, after, text, excerpt, clipped}`: `kind` is `text`, `formula` or `value`,
    `number` the match's place among those of its cell, `start`/`end` where it is in the cell's text, `parts` what
    the kept parts matched, `after` what a replacement would make of it (`null` for a value, or without one), `text`
    the stretch of the cell around it, `excerpt` the match inside that and `clipped` whether the cell goes on before
    and after it. `left_out` are cells that look like matches but fail a condition, `{sheet, row, col, kind, why}`.
    `counts` are cells with a match, by kind; `total` all matches, of which at most 2000 are listed. `pattern` is
    `{find, filter, replace}`, the three fields that say the same search as text. A search that cannot run — a
    mistake in the person's pattern, or one that could run without end — is not an error: it answers `error:
    {message, field, position}` and finds nothing, so that a client can say so while she types. `timed_out` says the
    search stopped before it had seen everything."""
    chosen, (sheets, area) = _kinds_of(kinds, "search_find"), _search_scope(ctx, scope, "search_find")
    try:
        compiled = _search_of(query)
    except SearchError as error:
        return _no_search(error, {"revision": _rev(ctx)})
    deadline = time.monotonic() + SEARCH_SECONDS
    found = scan(
        _workbook(ctx), compiled, kinds=chosen, sheets=sheets, area=area, time_up=lambda: time.monotonic() >= deadline
    )
    return {
        "revision": _rev(ctx),
        "matches": [
            {
                "sheet": h.sheet,
                "row": h.row,
                "col": h.col,
                "kind": h.kind,
                "number": h.number,
                "start": h.start,
                "end": h.end,
                "parts": list(h.kept),
                "after": h.after,
                "text": h.text,
                "excerpt": [h.excerpt_start, h.excerpt_end],
                "clipped": [h.clipped_before, h.clipped_after],
            }
            for h in found.matches
        ],
        "left_out": [
            {"sheet": o.sheet, "row": o.row, "col": o.col, "kind": o.kind, "why": o.why} for o in found.left_out
        ],
        "counts": found.counts,
        "total": found.total,
        "truncated": found.truncated,
        "timed_out": found.timed_out,
        "pattern": compiled.pattern_text(),
    }


def _left(items: list | None) -> dict[tuple[str, int, int], set[int] | None]:
    """The matches a person wants to keep, as ``{(sheet, row, col): {match numbers} | None}`` (``None``: the cell)."""
    leave: dict[tuple[str, int, int], set[int] | None] = {}
    for item in items or []:
        ok = isinstance(item, dict) and set(item) == {"sheet", "row", "col", "match"}
        if not ok or not isinstance(item["sheet"], str):
            raise RequestError("bad_request", "leave: each is {sheet, row, col, match}, match being a number or null")
        row, col, match = _index(item["row"], MAX_ROWS, "row"), _index(item["col"], MAX_COLS, "col"), item["match"]
        if match is not None and (isinstance(match, bool) or not isinstance(match, int) or match < 0):
            raise RequestError("bad_request", "leave: match is the number of a match in the cell, or null for all")
        key = (item["sheet"], row, col)
        if match is None:
            leave[key] = None
        elif leave.get(key, set()) is not None:
            leave[key] = {*(leave.get(key) or set()), match}
    return leave


def _plan(ctx, query: dict, kinds: list | None, scope: dict | None, leave: list | None, method: str) -> Plan:
    chosen, (sheets, area) = _kinds_of(kinds, method), _search_scope(ctx, scope, method)
    compiled = _search_of(query)
    return plan_replacement(
        _workbook(ctx),
        compiled,
        kinds=chosen,
        sheets=sheets,
        area=area,
        leave=_left(leave),
        held=_holder(ctx),
        max_length=ctx.limits.max_text,
    )


def _holder(ctx):
    """Who holds a cell, when it is somebody else: asks the document's locks once per sheet."""
    locks: dict[str, list] = {}

    def held(sheet: str, row: int, col: int) -> str | None:
        if sheet not in locks:
            whole = CellRegion.of(SheetId(sheet), 0, 0, MAX_ROWS - 1, MAX_COLS - 1)
            locks[sheet] = ctx.document.presence.conflicts(ctx.user, [whole])
        here = CellRegion.of(SheetId(sheet), row, col, row, col)
        return next((owner for owner, region in locks[sheet] if region.overlaps(here)), None)

    return held


def _skipped(plan: Plan) -> list[dict]:
    return [
        {"sheet": s.sheet, "row": s.row, "col": s.col, "kind": s.kind, "reason": s.reason, "by": s.by}
        for s in plan.skipped
    ]


@computes_methods.method("search_preview", "query:dict kinds:list? scope:dict? leave:list?")
def _search_preview(ctx, *, query, kinds, scope, leave):
    """What `search_replace` with the same parameters would do, without doing it: `{revision, changes, skipped,
    total}`. A change is `{sheet, row, col, kind, before, after}` (`kind` is `text` or `formula`; at most 2000 are
    listed, `total` is how many there are); a skipped cell is `{sheet, row, col, kind, reason, by}`, the reason being
    `locked` (`by` holds it), `formula` (the result would no longer be a formula that reads) or `too_long`. Only
    text and formulas are ever replaced, whatever `kinds` says. A query that cannot run answers `error` as
    `search_find` does."""
    try:
        plan = _plan(ctx, query, kinds, scope, leave, "search_preview")
    except SearchError as error:
        return {
            "revision": _rev(ctx),
            "error": {"message": error.message, "field": error.field, "position": error.position},
        }
    return {
        "revision": _rev(ctx),
        "changes": [
            {"sheet": c.sheet, "row": c.row, "col": c.col, "kind": c.kind, "before": c.before, "after": c.after}
            for c in plan.changes[:MAX_PREVIEWED]
        ],
        "skipped": _skipped(plan),
        "total": len(plan.changes),
    }


@computes_methods.method("search_replace", "query:dict kinds:list? scope:dict? leave:list? base:revision?", write=True)
def _search_replace(ctx, *, query, kinds, scope, leave, base):
    """Replace what `search_find` finds, with `query.replace` (the same parameters as `search_preview`, which shows
    the effect first). One change in the history, stored as the cells it changes: undoing it restores them all. Cells
    held by somebody else are skipped and named in `skipped`, never refused as a whole. Answers `{revision,
    replaced, skipped}`, `replaced` being the number of cells changed (nothing changing is not an error and leaves no
    entry in the history). `command_error` for a query that cannot run or has nothing to replace with, `bad_request`
    when more than 10000 cells would change."""
    plan = _plan(ctx, query, kinds, scope, leave, "search_replace")
    if len(plan.changes) > MAX_REPLACED_CELLS:
        raise RequestError(
            "bad_request",
            f"search_replace: that would change {len(plan.changes)} cells, at most {MAX_REPLACED_CELLS} at a time: "
            "narrow the search",
        )
    command = replace_command(plan)
    if command is None:
        return {"revision": _rev(ctx), "replaced": 0, "skipped": _skipped(plan)}
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), "replaced": len(plan.changes), "skipped": _skipped(plan)}
