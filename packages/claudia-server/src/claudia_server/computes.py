"""The methods of the spreadsheet app: what a table view needs to show cells and to take what people type (E3.1).

``computes_methods`` is ``core_methods`` plus ``sheets``, ``cells``, ``set_cells``, ``add_sheet``, ``structure``,
``sizes``, ``resize_lines``, ``objects``, ``images``, ``styles``, ``add_image``, ``move_object``,
``resize_object``, ``rotate_object``, ``remove_object``, ``diagrams``, ``charts``, ``chart_figure``,
``define_diagram``, ``update_diagram``, ``forget_diagram``, ``add_diagram_object``, ``add_chart``,
``remove_chart``, for named ranges, tables and queries (E6.5), ``names``, ``define_name``, ``rename_name``,
``remove_name``, ``sql_preview`` and ``define_sql``, for pivot tables (E6.30) ``pivots``, ``define_pivot``,
``update_pivot``, ``delete_pivot``, ``pivot_sql`` and ``pivot_to_sql``, and for search and replace (E6.20)
``search_find``, ``search_preview`` and ``search_replace`` (:mod:`claudia_server.computes_search`), and for printing
(E6.19) ``print_setup``, ``set_print_page``, ``set_sheet_print``, ``language`` and ``set_language``. Cells
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

A *pivot table* (E6.30, D620, D626) is a definition kept by name, shown by a ``PIVOT("name")`` formula in the cell
where it starts, as ``{name, definition, labels, anchor, region, a1, placed, error, header_rows, header_roles,
total_row, total_column}``: ``definition`` is :meth:`claudia_computes.PivotDefinition.to_data`, ``labels`` the words
it was made with, ``anchor`` the cell it starts in and ``region`` the cells it fills now (``{sheet, row0, col0, row1,
col1}``, ``null`` when it fills none); ``placed`` is false when its cell was overwritten. Its cells are ordinary
spilled cells; ``header_roles`` tells a client what each cell of the header rows is for (``corner``, ``field``,
``header``) and the rest follows from ``total_row`` and ``total_column``: the first column is ``label`` (``total`` on
the total row), the others ``value`` (``total`` on the total row and in the total column).

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

import time
from collections import Counter
from functools import lru_cache

from claudia_computes_io import (
    Untranslatable,
    apply_edits_to_ods,
    apply_edits_to_xlsx,
    ods_export_losses,
    ods_unwritten_changes,
    workbook_to_ods,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_unwritten_changes,
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
    FunctionHelp,
    InsertCols,
    InsertRows,
    NamedRange,
    PivotDefinition,
    PivotError,
    PivotLabels,
    PrintSetupError,
    RemoveChart,
    RemoveName,
    RenameName,
    Resample,
    ResizeLines,
    SetCells,
    SetCellStyle,
    SetPrintPage,
    SetRandomSeed,
    SetSheetPrint,
    SheetId,
    SheetPrintSetup,
    Structure,
    WorkbookModel,
    create_pivot,
    delete_pivot,
    function_catalog,
    get_function,
    parse_input,
    pivot_to_sql,
    search_functions,
    update_pivot,
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
from claudia_computes.names import PURPOSES, key_of  # noqa: F401
from claudia_computes.refs import CellRef, RangeRef
from claudia_computes.trace import REACHES
from claudia_computes.values import ErrorValue, FormulaError
from claudia_core import (
    AddObject,
    Batch,
    Command,
    DefineDiagram,
    DescribeThing,
    ForgetDiagram,
    ObjectBody,
    PageSetup,
    PageSetupError,
    UpdateDiagram,
    clean_name,
    name_problem,
)

from .computes_search import add_search_methods
from .i18n import msg, translate
from .object_methods import Placement, add_object_methods
from .office_export import document_info, export_with_original, office_export
from .printing import add_language_methods, people_only
from .protocol import Context, RequestError, core_methods
from .rendered import add_rendering_methods
from .replay import add_replay_methods
from .style_targets import OBJECTS
from .styles import add_style_methods
from .thing_names import add_name_methods, default_name
from .wire import current_revision, done, fresh_id

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
add_name_methods(computes_methods)
add_replay_methods(computes_methods)


def _workbook(ctx: Context) -> WorkbookModel:
    model = ctx.document.model
    if not isinstance(model, WorkbookModel):
        raise RequestError("command_error", msg("this document is not a workbook"))
    return model


add_search_methods(computes_methods, workbook=_workbook)
add_language_methods(computes_methods)  # ``language`` and ``set_language``: the layout hyphenates by it (D915)


def _index(value, limit: int, what: str):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < limit:
        raise RequestError(
            "bad_request", msg("{what} must be a whole number from 0 to {last}", what=what, last=limit - 1)
        )
    return value


def _fresh_range_id(workbook: WorkbookModel) -> str:
    """A fresh id for a named range (D552): the id a tag in the chat points at, which a rename of the name leaves
    alone."""
    return fresh_id("r", {thing for _kind, thing, _name in workbook.named_things()})


def _diagram_definition(workbook: WorkbookModel, diagram_id: str, what: str) -> None:
    if diagram_id not in workbook.diagrams:
        raise RequestError(
            "command_error",
            msg("{what}: this document does not know the diagram {diagram_id!r}", what=what, diagram_id=diagram_id),
        )


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
        raise RequestError("bad_request", msg('export_office: format must be "xlsx" or "ods"'))
    book = _workbook(ctx)
    info = document_info(ctx.document.log, ctx.document.branch)
    draw = None if ctx.renderings is None else ctx.renderings.rasteriser  # draws an SVG picture as a PNG (D464)
    if format == "xlsx":
        return export_with_original(
            ctx,
            format,
            WorkbookModel,
            lambda original, baseline, current, found: apply_edits_to_xlsx(original, baseline, current, losses=found),
            lambda: office_export(
                format,
                workbook_to_xlsx(book, info=info, rasterise=draw),
                xlsx_export_losses(book, rasterised=draw is not None),
            ),
            xlsx_unwritten_changes,
        )
    return export_with_original(
        ctx,
        format,
        WorkbookModel,
        lambda original, baseline, current, found: apply_edits_to_ods(
            original, baseline, current, losses=found, info=info
        ),
        lambda: office_export(
            format,
            workbook_to_ods(book, info=info, rasterise=draw),
            ods_export_losses(book, rasterised=draw is not None),
        ),
        ods_unwritten_changes,
    )


MAX_RESAMPLE = 1_000  # draws one ``resample`` may skip
MAX_SEED = 2**53  # a seed a JSON number holds exactly


def _whole(value, low: int, high: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RequestError(
            "bad_request", msg("{what} must be a whole number from {low} to {high}", what=what, low=low, high=high)
        )
    return value


@computes_methods.method("random_state")
def _random_state(ctx):
    """What every random number in the workbook is a function of (E6.22, D291): `{revision, seed, draw}`. All
    users see the same numbers because they share both."""
    book = _workbook(ctx)
    return {"revision": current_revision(ctx), "seed": book.random_seed, "draw": book.random_draw}


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
    return done(ctx, SetRandomSeed(seed), base)


@computes_methods.method("print_setup")
def _print_setup(ctx):
    """How the workbook is printed (E6.19, D1004): `{revision, page, sheets}`. `page` is as composes' `page`
    (paper, width, height, orientation, margins, page_numbers; lengths in mpt) and the same for all sheets; `sheets`
    holds, for every sheet and chart tab by id, its own setup — `{orientation, scale, order, repeat_rows,
    repeat_cols, gridlines, headings, purposes, footer_name, objects, skip_empty}` — with the defaults filled in
    for one nobody has set up. `scale` is `{kind: "fit-width" | "fit-page"}` or `{kind: "percent", percent}`
    (10 to 400); `repeat_rows` and `repeat_cols` are `[first, last]` (from 0) or `null`. The print area is a named
    range (E6.19.5), not part of this."""
    book = _workbook(ctx)
    return {
        "revision": current_revision(ctx),
        "page": book.print_page.to_data(),
        "sheets": {str(key): book.sheet_print_of(str(key)).to_data() for key in (*book.sheets, *book.charts)},
    }


@computes_methods.method("set_print_page", "page:dict base:revision?", write=True)
def _set_print_page(ctx, *, page, base):
    """Print the workbook on another page (`page` as `print_setup` returns it). One step for everybody, in the
    history. `command_error` names what is wrong with a page that cannot be used."""
    people_only(ctx)
    try:
        command = SetPrintPage(PageSetup.from_data(page))
    except PageSetupError as exc:
        raise RequestError("command_error", str(exc)) from None
    return done(ctx, command, base)


@computes_methods.method("set_sheet_print", "sheet:str setup:dict base:revision?", write=True)
def _set_sheet_print(ctx, *, sheet, setup, base):
    """Print a sheet or chart tab another way (`sheet` its id, `setup` as `print_setup` returns it; a part that is
    left out has its default). One step for everybody, in the history. `command_error` for an unknown sheet or a
    setup that cannot be used."""
    people_only(ctx)
    try:
        command = SetSheetPrint(sheet, SheetPrintSetup.from_data(setup))
    except PrintSetupError as exc:
        raise RequestError("command_error", str(exc)) from None
    return done(ctx, command, base)


MAX_PREVIEW_DRAWS = 1_000  # draws in one ``random_preview``


def _number_text(value: float) -> str:
    """A number as a formula writes it: ``1000`` and not ``1000.0``."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _limit(value, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError("bad_request", msg("random_preview: {what} must be a number or null", what=what))
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
        raise RequestError("bad_request", msg("random_preview: params must be numbers"))
    low, high = _limit(low, "low"), _limit(high, "high")
    known = DISTRIBUTIONS.get(distribution.casefold()) if isinstance(distribution, str) else None
    if known is None:
        raise RequestError(
            "bad_request", msg("random_preview: there is no distribution {distribution!r}", distribution=distribution)
        )
    try:
        check_parameters(known, params)
        points = [quantile(known.name, (i + 0.5) / draws, params, low=low, high=high) for i in range(draws)]
    except FormulaError as exc:
        raise RequestError("command_error", msg("random_preview: {problem}", problem=exc.detail or exc.code)) from None
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
        raise RequestError("bad_request", msg('outcome_table: combine must be "all" or "pair"'))
    try:
        table = _workbook(ctx).outcome_table(SheetId(sheet), row, col, combine=combine)
    except (KeyError, ValueError) as exc:
        raise RequestError("command_error", str(exc)) from None
    return {"revision": current_revision(ctx), "table": None if table is None else table.to_data()}


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
        raise RequestError("bad_request", msg("trace: reach must be one of {reaches}", reaches=", ".join(REACHES)))
    area = None
    if window is not None:
        if not isinstance(window, list) or len(window) != 4:
            raise RequestError("bad_request", msg("trace: window is [row0, col0, row1, col1]"))
        r0, c0 = _index(window[0], MAX_ROWS, "window row0"), _index(window[1], MAX_COLS, "window col0")
        r1, c1 = _index(window[2], MAX_ROWS, "window row1"), _index(window[3], MAX_COLS, "window col1")
        if r1 < r0 or c1 < c0:
            raise RequestError("bad_request", msg("trace: the window must not end before it starts"))
        if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_WINDOW_CELLS:
            raise RequestError(
                "bad_request", msg("trace: window too large (at most {limit} positions)", limit=MAX_WINDOW_CELLS)
            )
        area = (r0, c0, r1, c1)
    try:
        found = _workbook(ctx).trace(SheetId(sheet), row, col, reach=reach, window=area)
    except KeyError as exc:
        raise RequestError("command_error", str(exc)) from None
    return {"revision": current_revision(ctx), "trace": found.to_data()}


@computes_methods.method("cells", "sheet:str row0:int row1:int col0:int col1:int")
def _cells(ctx, *, sheet, row0, row1, col0, col1):
    """The cells that hold something in a window of a sheet (both ends included), sorted by row and column, as
    `{revision, cells: [[row, col, content]]}`; a formula comes with its value and, under `f`, its text. A window has at
    most 50000 positions; ask for what is visible."""
    row0, row1 = _index(row0, MAX_ROWS, "row0"), _index(row1, MAX_ROWS, "row1")
    col0, col1 = _index(col0, MAX_COLS, "col0"), _index(col1, MAX_COLS, "col1")
    if row1 < row0 or col1 < col0:
        raise RequestError("bad_request", msg("cells: the window must not end before it starts"))
    if (row1 - row0 + 1) * (col1 - col0 + 1) > MAX_WINDOW_CELLS:
        raise RequestError(
            "bad_request",
            msg("cells: window too large (at most {limit} positions)", limit=MAX_WINDOW_CELLS),
        )
    found = _workbook(ctx).sheet(sheet)
    inside = found.cells_in(row0, row1, col0, col1)
    return {"revision": current_revision(ctx), "cells": [[r, c, found.view((r, c))] for r, c in inside]}


def _typed(ctx, items: list) -> tuple[tuple[int, int, dict | None], ...]:
    if len(items) > MAX_TYPED_CELLS:
        raise RequestError("bad_request", msg("set_cells: at most {limit} cells at a time", limit=MAX_TYPED_CELLS))
    cells = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"row", "col", "input"}:
            raise RequestError("bad_request", msg("set_cells: each cell is an object with row, col and input"))
        text = item["input"]
        if not isinstance(text, str) or len(text) > ctx.limits.max_text:
            raise RequestError(
                "bad_request",
                msg("set_cells: input must be text of at most {limit} characters", limit=ctx.limits.max_text),
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
        raise RequestError("bad_request", msg("cell_styles: the window must not end before it starts"))
    found = _workbook(ctx).sheet(sheet)
    return {"revision": current_revision(ctx), "ranges": found.cell_styles.ranges_in((row0, col0, row1, col1))}


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
    return done(ctx, SetCells(sheet, _typed(ctx, cells)), base)


def _fresh_sheet_id(taken) -> str:
    """The next sheet id (``s2``, ``s3`` ...) that no sheet of the workbook has."""
    number = len(taken) + 1
    while f"s{number}" in taken:
        number += 1
    return f"s{number}"


@computes_methods.method("add_sheet", "name:str base:revision?", write=True)
def _add_sheet(ctx, name, base):
    """Add a sheet at the end. The name must be new (case does not matter) and not empty. Returns the new sheet's id
    and the revision."""
    name = name.strip()
    if not name or len(name) > MAX_SHEET_NAME:
        raise RequestError(
            "bad_request",
            msg("add_sheet: the name must have 1 to {limit} characters", limit=MAX_SHEET_NAME),
        )
    sheet_id = _fresh_sheet_id(_workbook(ctx).sheets)
    return done(ctx, AddSheet(SheetId(sheet_id), name), base, sheet=sheet_id)


@computes_methods.method("structure", "sheet:str axis:str insert:bool at:int count:int=1 base:revision?", write=True)
def _structure(ctx, *, sheet, axis, insert, at, count, base):
    """Insert or delete `count` rows or columns (`axis` is "row" or "col") at index `at`; cells move with them.
    Colleagues' places in the sheet move too."""
    edit = AXES.get((axis, insert))
    if edit is None:
        raise RequestError("bad_request", msg('structure: axis must be "row" or "col"'))
    return done(ctx, Structure(edit(sheet, at, count)), base)


@computes_methods.method("sizes", "sheet:str")
def _sizes(ctx, *, sheet):
    """The rows and columns of a sheet that were given a size away from the default (D135), as
    `{revision, rows: [[row, height]], cols: [[col, width]]}`, each sorted by index. A line not listed shows at the
    sheet's default (`DEFAULT_ROW_HEIGHT`/`DEFAULT_COL_WIDTH` in `claudia_computes.model`)."""
    found = _workbook(ctx).sheet(sheet)
    return {
        "revision": current_revision(ctx),
        "rows": [[r, h] for r, h in sorted(found.row_heights.items())],
        "cols": [[c, w] for c, w in sorted(found.col_widths.items())],
    }


def _sized(axis: str, items: list) -> tuple[tuple[int, float | None], ...]:
    if len(items) > MAX_RESIZED_LINES:
        raise RequestError(
            "bad_request",
            msg("resize_lines: at most {limit} lines at a time", limit=MAX_RESIZED_LINES),
        )
    limit = MAX_ROWS if axis == "row" else MAX_COLS
    lo, hi = SIZE_LIMITS[axis]
    sizes = []
    for item in items:
        if not (isinstance(item, list) and len(item) == 2):
            raise RequestError("bad_request", msg("resize_lines: each line is [index, size]"))
        index, size = item
        index = _index(index, limit, "index")
        if size is not None:
            if isinstance(size, bool) or not isinstance(size, (int, float)):
                raise RequestError("bad_request", msg("resize_lines: size must be a number or null"))
            if not lo <= size <= hi:
                raise RequestError("bad_request", msg("resize_lines: size must be between {lo} and {hi}", lo=lo, hi=hi))
        sizes.append((index, None if size is None else float(size)))
    return tuple(sizes)


@computes_methods.method("resize_lines", "sheet:str axis:str sizes:list base:revision?", write=True)
def _resize_lines(ctx, *, sheet, axis, sizes, base):
    """Set (or clear, with `null`) the height of rows or the width of columns: `axis` is "row" or "col", `sizes` a
    list of `[index, size]`. One change in the history. Same errors as `apply`."""
    if axis not in SIZE_LIMITS:
        raise RequestError("bad_request", msg('resize_lines: axis must be "row" or "col"'))
    return done(ctx, ResizeLines(sheet, axis, _sized(axis, sizes)), base)


@computes_methods.method("objects", "sheet:str")
def _objects(ctx, *, sheet):
    """The floating objects of a sheet, the one in front last, as `{revision, sheet, objects}`. An object is
    `{id, sheet, kind, row, col, w, h, image, imported}`, anchored to the cell at (`row`, `col`) with a pixel
    size that never changes on its own: inserting, deleting or resizing rows/columns never moves or resizes it,
    only `move_object` does. `imported`'s `source_path` is only sent to the person who imported that image
    (everyone else sees `null` there, not the path)."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", msg("unknown sheet {sheet!r}", sheet=sheet))
    objects = [obj.to_data_for(ctx.user) for obj in workbook.objects_on(sheet)]
    return {"revision": current_revision(ctx), "sheet": sheet, "objects": objects}


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
    return {"revision": current_revision(ctx), "figure": workbook.chart_figure(diagram)}


@computes_methods.method("define_diagram", "definition:dict base:revision?", write=True)
def _define_diagram(ctx, *, definition, base):
    """Take a new chart definition into the document: `definition` is `{kind, range, series_in, title, x_title,
    y_title, legend, gridlines}` (E6.6); give `source` (and `source_scope`) instead of `range` to draw a named
    table or `SQL()` result that the chart then follows as it grows or moves (E6.5) — the id and format are this
    server's to assign, not the client's, so neither is sent. Returns the new definition's id and the revision;
    show it with `add_diagram_object`, `add_chart`, or both."""
    if "id" in definition or "format" in definition:
        raise RequestError("bad_request", msg("define_diagram: id and format are assigned by the server"))
    workbook = _workbook(ctx)
    diagram_id = fresh_id("g", workbook.diagrams)
    command = DefineDiagram({**definition, "id": diagram_id, "format": 1})
    return done(ctx, command, base, diagram=diagram_id)


@computes_methods.method("update_diagram", "id:str definition:dict base:revision?", write=True)
def _update_diagram(ctx, *, id, definition, base):
    """Redefine a chart in place (E6.6): what a tab or floating object already showing `id` updates to, with
    nothing to re-place. Same shape as `define_diagram`'s `definition`; the id and format are unchanged."""
    _diagram_definition(_workbook(ctx), id, "update_diagram")
    command = UpdateDiagram(id, {**definition, "id": id, "format": 1})
    return done(ctx, command, base)


@computes_methods.method("forget_diagram", "id:str base:revision?", write=True)
def _forget_diagram(ctx, *, id, base):
    """Let a chart definition go. Refused while a tab or a floating object still shows it — remove or repoint
    those first (`remove_chart`, `remove_object`, or `update_diagram`/`add_chart` onto another definition)."""
    return done(ctx, ForgetDiagram(id), base)


@computes_methods.method(
    "add_diagram_object", "sheet:str row:int col:int w:int h:int diagram:str base:revision?", write=True
)
def _add_diagram_object(ctx, *, sheet, row, col, w, h, diagram, base):
    """Put a chart on a sheet as a floating object, showing the definition `diagram` already names
    (`define_diagram`). Returns the new object's id and the revision; `move_object`/`resize_object`/
    `rotate_object`/`remove_object` then work on it exactly as they do on any other object."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", msg("unknown sheet {sheet!r}", sheet=sheet))
    _diagram_definition(workbook, diagram, "add_diagram_object")
    object_id = fresh_id("o", workbook.objects)
    body = ObjectBody(object_id, "diagram", w, h, "plain-image", ref=diagram, name=default_name(ctx, "diagram"))
    command = AddObject(body, CellAnchor(SheetId(sheet), row, col).to_data())
    return done(ctx, command, base, object=object_id)


@computes_methods.method("add_chart", "name:str spec_id:str index:int? base:revision?", write=True)
def _add_chart(ctx, *, name, spec_id, index, base):
    """Add a chart tab showing the definition `spec_id` already names (`define_diagram`); `index` is where in
    the tab order (the end, if omitted). Returns the new tab's id and the revision."""
    name = name.strip()
    if not name or len(name) > MAX_SHEET_NAME:
        raise RequestError(
            "bad_request",
            msg("add_chart: the name must have 1 to {limit} characters", limit=MAX_SHEET_NAME),
        )
    workbook = _workbook(ctx)
    _diagram_definition(workbook, spec_id, "add_chart")
    chart_id = fresh_id("t", workbook.charts)
    return done(ctx, AddChart(chart_id, name, spec_id, index), base, chart=chart_id)


@computes_methods.method("remove_chart", "id:str base:revision?", write=True)
def _remove_chart(ctx, *, id, base):
    """Remove a chart tab. The definition it showed is untouched — it may still be shown elsewhere
    (`forget_diagram` is the separate, explicit step for letting the definition itself go)."""
    return done(ctx, RemoveChart(id), base)


@lru_cache(maxsize=8)
def _catalog_in(locale: str) -> list[FunctionHelp]:
    """The function catalog with its words in the language of ``locale`` (English where there is no translation);
    built once per language, since it is the same for every document and every window."""
    return [entry.translated(lambda text: translate(text, locale)) for entry in function_catalog()]


def _function_summary(entry) -> dict:
    return {"name": entry.name, "signature": entry.signature, "tooltip": entry.tooltip}


@computes_methods.method("functions", 'query:str=""')
def _functions(ctx, *, query):
    """Every cell function whose name or description mentions `query` (case-insensitive), closest name match
    first; every function, alphabetically, if `query` is blank (E13.5/E13.6: the searchable function list). Each
    result is `{name, signature, tooltip}`; fetch the full help text with `function_help`. The descriptions are in
    the language of the connection where they have been translated (E13.8), English where not."""
    return [_function_summary(entry) for entry in search_functions(query, _catalog_in(ctx.locale))]


@computes_methods.method("function_help", "name:str")
def _function_help(ctx, *, name):
    """One function's full help text, by the name a `functions` result gave (while typing, the formula bar asks
    for this itself: E13.5's "in context" is the signature and a short example shown as you type). In the language
    of the connection where it has been translated, English where not."""
    entry = get_function(name, _catalog_in(ctx.locale))
    if entry is None:
        raise RequestError("command_error", msg("no function named {name!r}", name=name))
    return {"name": entry.name, "signature": entry.signature, "tooltip": entry.tooltip, "help": entry.help}


# ------------------------------------------------------------------------------------ names, tables, queries (E6.5)
MAX_PREVIEW_ROWS = 50


def _scope_of(workbook: WorkbookModel, value, what: str) -> SheetId | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in workbook.sheets:
        raise RequestError("bad_request", msg("{what}: scope must be a sheet id or null", what=what))
    return SheetId(value)


def _cell_range(workbook: WorkbookModel, data, what: str) -> RangeRef:
    if not isinstance(data, dict) or set(data) != {"sheet", "row0", "col0", "row1", "col1"}:
        raise RequestError("bad_request", msg("{what}: range is {{sheet, row0, col0, row1, col1}}", what=what))
    sheet = data["sheet"]
    if sheet not in workbook.sheets:
        raise RequestError(
            "bad_request", msg("{what}: this document does not know the sheet {sheet!r}", what=what, sheet=sheet)
        )
    r0, c0 = _index(data["row0"], MAX_ROWS, "row0"), _index(data["col0"], MAX_COLS, "col0")
    r1, c1 = _index(data["row1"], MAX_ROWS, "row1"), _index(data["col1"], MAX_COLS, "col1")
    if r1 < r0 or c1 < c0:
        raise RequestError("bad_request", msg("{what}: the range must not end before it starts", what=what))
    return RangeRef(CellRef(r0, c0, SheetId(sheet)), CellRef(r1, c1, SheetId(sheet)))


def _anchor_of(workbook: WorkbookModel, data, what: str) -> tuple[SheetId, int, int]:
    if not isinstance(data, dict) or set(data) != {"sheet", "row", "col"} or data["sheet"] not in workbook.sheets:
        raise RequestError(
            "bad_request", msg("{what}: anchor is {{sheet, row, col}} on a sheet of this document", what=what)
        )
    return SheetId(data["sheet"]), _index(data["row"], MAX_ROWS, "row"), _index(data["col"], MAX_COLS, "col")


def _name_from(workbook: WorkbookModel, definition: dict, what: str) -> NamedRange:
    """A :class:`NamedRange` from what a client sends; ``bad_request`` for anything that is not one."""
    allowed = {"name", "scope", "range", "anchor", "header", "grows", "purpose", "column_purposes"}
    if not isinstance(definition, dict) or not set(definition) <= allowed or "name" not in definition:
        raise RequestError(
            "bad_request", msg("{what}: the definition is an object with {allowed}", what=what, allowed=sorted(allowed))
        )
    anchor, given = definition.get("anchor"), definition.get("range")
    if (given is None) == (anchor is None):
        raise RequestError(
            "bad_request", msg("{what}: give a range or an anchor (the cell of a SQL() formula), not both", what=what)
        )
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
            _fresh_range_id(workbook),
        )
    except (ValueError, TypeError) as problem:
        raise RequestError("bad_request", msg("{what}: {problem}", what=what, problem=problem)) from None


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
        "id": named.id,
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


@computes_methods.method("number_formats")
def _number_formats(ctx):
    """The workbook's named number formats (D378), as `[{id, name, code, to_name}]`: a cell shows its number through
    the format its words' style names (a style's `number_format`, inherited from its parent where it sets none).
    `code` is Excel's format code; the client renders it in the reader's locale."""
    return _workbook(ctx).number_formats.to_data()


@computes_methods.method("names")
def _names(ctx):
    """Every name of the workbook (named ranges, tables and query results), workbook-wide ones first, as
    `{revision, names: [{id, name, scope, kind, header, grows, purpose, column_purposes, sheet, sheet_name, region, a1,
    anchor, columns, rows}]}`. `columns` are the columns as a query names them, with their type (`int`, `real`,
    `text` or `mixed`) and purpose; `rows` the data rows. Ask again after a `names` push event."""
    workbook = _workbook(ctx)
    return {
        "revision": current_revision(ctx),
        "names": [_name_data(workbook, named) for named in workbook.names.sorted()],
    }


@computes_methods.method("define_name", "definition:dict base:revision?", write=True)
def _define_name(ctx, *, definition, base):
    """Give cells a name, or point an existing name (same scope, any case) somewhere else. `definition` is `{name,
    scope?, range, header?, grows?, purpose?, column_purposes?}` with `range` as `{sheet, row0, col0, row1, col1}`
    (header row included), or `anchor` as `{sheet, row, col}` in place of `range` for the result of a `SQL()` cell.
    `purpose` is `input`, `data`, `calc` or `result`; `column_purposes` is `[[offset, purpose]]`. A name is a word
    that is not a cell address. One change in the history."""
    named = _name_from(_workbook(ctx), definition, "define_name")
    return done(ctx, DefineName(named), base)


@computes_methods.method("name_and_describe_range", "range:dict name:str description:text base:revision?", write=True)
def _name_and_describe_range(ctx, *, range, name, description, base):  # noqa: A002 - the wire name
    """The Name & describe… dialog for cells that have no name yet (D1317): give the cells `range` (`{sheet, row0,
    col0, row1, col1}`) the name `name` and the description `description`, as one step in the history, so one Undo takes
    both back. A range is not a thing until it has a name, so the name is required (`bad_request` without text,
    `command_error` when somebody else has it, as for `define_name`). Returns `{revision, id, name}`: the id is the one
    to give `name_and_describe` from then on."""
    problem = name_problem(name)
    if problem is not None:
        raise RequestError("bad_request", problem)
    named = _name_from(_workbook(ctx), {"name": clean_name(name), "range": range}, "name_and_describe_range")
    steps: list[Command] = [DefineName(named)]
    if description:
        steps.append(DescribeThing(named.id, description))
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Name and describe")
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), "id": named.id, "name": named.name}


@computes_methods.method("rename_name", "old:str new:str scope:str? base:revision?", write=True)
def _rename_name(ctx, *, old, new, scope, base):
    """Call a name something else; the formulas that use it are rewritten. `scope` is the sheet id the name is
    scoped to, or null for a workbook-wide one."""
    scope_id = _scope_of(_workbook(ctx), scope, "rename_name")
    return done(ctx, RenameName(scope_id, old, new), base)


@computes_methods.method("remove_name", "name:str scope:str? base:revision?", write=True)
def _remove_name(ctx, *, name, scope, base):
    """Take a name away. The cells stay; formulas that used the name show `#NAME?`."""
    scope_id = _scope_of(_workbook(ctx), scope, "remove_name")
    return done(ctx, RemoveName(scope_id, name), base)


@computes_methods.method("sql_preview", "query:str sheet:str limit:int=20")
def _sql_preview(ctx, *, query, sheet, limit):
    """Run a query as a `SQL()` cell on `sheet` would, without changing the document: `{ok: true, columns, rows,
    row_count, ms}` with at most `limit` rows, or `{ok: false, error: {code, detail}}` — the same `#SQL!` a cell would
    show. The same limits apply as in a cell (read only, one second, 100000 rows)."""
    workbook = _workbook(ctx)
    if sheet not in workbook.sheets:
        raise RequestError("command_error", msg("unknown sheet {sheet!r}", sheet=sheet))
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= MAX_PREVIEW_ROWS:
        raise RequestError(
            "bad_request",
            msg(
                "sql_preview: limit must be a whole number from 0 to {limit}",
                limit=MAX_PREVIEW_ROWS,
            ),
        )
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
        raise RequestError("command_error", msg("unknown sheet {sheet!r}", sheet=sheet))
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    if not isinstance(query, str) or not query.strip() or len(query) > ctx.limits.max_text:
        raise RequestError(
            "bad_request",
            msg("define_sql: query must be text of at most {limit} characters", limit=ctx.limits.max_text),
        )
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
            steps.append(
                DefineName(NamedRange(name, None, None, True, False, "result", (), anchor, _fresh_range_id(workbook)))
            )
        except ValueError as problem:
            raise RequestError("bad_request", msg("define_sql: {problem}", problem=problem)) from None
    return done(ctx, steps[0] if len(steps) == 1 else Batch(tuple(steps)), base)


# ---------------------------------------------------------------------------------------------- pivot tables
def _pivot_data(workbook: WorkbookModel, entry) -> dict:
    """One pivot as a client is sent it (see the module documentation)."""
    named = workbook.names.get(key_of(None, entry.name))
    anchor = None if named is None or named.anchor is None else named.anchor
    region = None if named is None else workbook.region_of(named)
    result = workbook.pivots.result(entry.name)
    error = None
    if anchor is not None:
        shown = workbook.value(*anchor)
        if isinstance(shown, ErrorValue):
            error = {"code": shown.code, "detail": shown.detail}
    a1 = None
    if region is not None:
        sheet_id, r0, c0, r1, c1 = region
        a1 = RangeRef(CellRef(r0, c0, sheet_id), CellRef(r1, c1, sheet_id)).to_a1(workbook.sheet_name_of)
    placed = False
    if anchor is not None and anchor[0] in workbook.sheets:
        content = workbook.sheet(anchor[0]).cells.get((anchor[1], anchor[2]))
        placed = content is not None and content.get("t") == "formula" and "PIVOT(" in str(content.get("v", "")).upper()
    return {
        "name": entry.name,
        "definition": entry.definition.to_data(),
        "labels": entry.labels.to_data(),
        "anchor": None if anchor is None else {"sheet": anchor[0], "row": anchor[1], "col": anchor[2]},
        "region": None
        if region is None or result is None
        else {"sheet": region[0], "row0": region[1], "col0": region[2], "row1": region[3], "col1": region[4]},
        "a1": a1 if result is not None else None,
        "placed": placed,
        "error": error,
        "header_rows": 0 if result is None else result.header_rows,
        "header_roles": []
        if result is None
        else [[role.value for role in row] for row in result.roles[: result.header_rows]],
        "total_row": False if result is None else result.total_row,
        "total_column": False if result is None else result.total_column,
    }


def _pivot_definition(data, what: str) -> PivotDefinition:
    try:
        return PivotDefinition.from_data(data)
    except PivotError as problem:
        raise RequestError("bad_request", msg("{what}: {problem}", what=what, problem=problem)) from None


def _pivot_labels(data, what: str) -> PivotLabels | None:
    if data is None:
        return None
    try:
        return PivotLabels.from_data(data)
    except PivotError as problem:
        raise RequestError("bad_request", msg("{what}: {problem}", what=what, problem=problem)) from None


def _refused(problem: ValueError):
    return RequestError("command_error", msg("{problem}", problem=problem))


@computes_methods.method("pivots")
def _pivots(ctx):
    """Every pivot table of the workbook, by name, as `{revision, pivots: [{name, definition, labels, anchor, region,
    a1, placed, error, header_rows, header_roles, total_row, total_column}]}` (see the module documentation).
    `error` is `{code, detail}` when the pivot's cell shows an error (`#SQL!` for a field or a source that is not
    there). Ask again after a `pivots` push event and after a `cells` event on a pivot's sheet: its region grows and
    shrinks with its source."""
    workbook = _workbook(ctx)
    return {
        "revision": current_revision(ctx),
        "pivots": [_pivot_data(workbook, entry) for entry in workbook.pivots.sorted()],
    }


@computes_methods.method(
    "define_pivot",
    "name:str definition:dict labels:dict? sheet:str? row:int=0 col:int=0 new_sheet:str? base:revision?",
    write=True,
)
def _define_pivot(ctx, *, name, definition, labels, sheet, row, col, new_sheet, base):
    """Make a pivot table called `name` (a name of the workbook: a word that is not a cell address) from
    `definition` (`{format: 1, source, rows, columns, values: [{field, aggregation, name}], filters, total_row,
    total_column}`; `source` is the name of a table, range or query result, the fields are its columns). It starts in
    the cell (`row`, `col`) of `sheet`, or of a sheet it makes called `new_sheet` (give one of the two); `labels`
    are the words it writes into its cells (`{total, blank, row_header, sum_of, count_of, average_of, min_of,
    max_of}`, `{field}` standing for the field's name) in the person's language, English where not given. One change
    in the history. Returns `{revision, sheet}`."""
    workbook = _workbook(ctx)
    if (sheet is None) == (new_sheet is None):
        raise RequestError("bad_request", msg("define_pivot: give the sheet it starts on or new_sheet, not both"))
    row, col = _index(row, MAX_ROWS, "row"), _index(col, MAX_COLS, "col")
    parsed, words = _pivot_definition(definition, "define_pivot"), _pivot_labels(labels, "define_pivot")
    if new_sheet is None:
        target = sheet
    else:
        new_sheet = new_sheet.strip()
        if not new_sheet or len(new_sheet) > MAX_SHEET_NAME:
            raise RequestError(
                "bad_request",
                msg("define_pivot: the name of the new sheet must have 1 to {limit} characters", limit=MAX_SHEET_NAME),
            )
        target = _fresh_sheet_id(workbook.sheets)
    try:
        command = create_pivot(workbook, name, (SheetId(target), row, col), parsed, words, new_sheet)
    except ValueError as problem:
        raise _refused(problem) from None
    return done(ctx, command, base, sheet=target)


@computes_methods.method("update_pivot", "name:str definition:dict labels:dict? base:revision?", write=True)
def _update_pivot(ctx, *, name, definition, labels, base):
    """Change what the pivot table `name` is made from (`definition` as in `define_pivot`); its cells follow. `labels`
    gives new words (`{}` the English ones); without it the words stay. One change in the history."""
    workbook = _workbook(ctx)
    parsed, words = _pivot_definition(definition, "update_pivot"), _pivot_labels(labels, "update_pivot")
    try:
        command = update_pivot(workbook, name, parsed, words)
    except ValueError as problem:
        raise _refused(problem) from None
    return done(ctx, command, base)


@computes_methods.method("delete_pivot", "name:str base:revision?", write=True)
def _delete_pivot(ctx, *, name, base):
    """Delete the pivot table `name`: its cells are empty, its name and definition gone. One change in the history."""
    try:
        command = delete_pivot(_workbook(ctx), name)
    except ValueError as problem:
        raise _refused(problem) from None
    return done(ctx, command, base)


@computes_methods.method("pivot_sql", "name:str")
def _pivot_sql(ctx, *, name):
    """The SQL query the pivot table `name` is, as `{sql}`: what it asks of its source, read only. Run as a `SQL()`
    formula it gives the same numbers (one header row). `command_error` for a pivot that gave nothing."""
    workbook = _workbook(ctx)
    entry = workbook.pivots.get(name)
    if entry is None:
        raise RequestError("command_error", msg("there is no pivot table called {name!r}", name=name))
    result = workbook.pivots.result(entry.name)
    if result is None or not result.sql:
        raise RequestError(
            "command_error", msg("the pivot table {name} gave nothing: there is no SQL to show", name=entry.name)
        )
    return {"sql": result.sql}


@computes_methods.method("pivot_to_sql", "name:str base:revision?", write=True)
def _pivot_to_sql(ctx, *, name, base):
    """Turn the pivot table `name` into the `SQL()` query it is: the cell it starts in holds the query, the name is
    the query's result now and the pivot is gone, as one change in the history (undo brings the pivot back). The cells
    are what the query gives: one header row, then the rows."""
    try:
        command = pivot_to_sql(_workbook(ctx), name)
    except ValueError as problem:
        raise _refused(problem) from None
    return done(ctx, command, base)


def _at_cell(workbook: WorkbookModel, held, *, row: int, col: int, sheet: str | None = None) -> dict:
    """Where an object of a workbook is: a cell of a sheet. A new one names its sheet; a moved one stays on its own."""
    if held is not None:
        sheet = held.sheet
    elif sheet not in workbook.sheets:
        raise RequestError("command_error", msg("unknown sheet {sheet!r}", sheet=sheet))
    return CellAnchor(SheetId(sheet), row, col).to_data()


CELLS = Placement(
    new="sheet:str row:int col:int",
    move="row:int col:int",
    frame="row:int col:int",
    anchor=_at_cell,
    says={
        "add_image": "`row` and `col` name the cell it hangs from; its pixel size (and anchor) never change on their "
        "own afterwards.",
        "move_object": "`row` and `col` name the cell it hangs from now.",
        "resize_object": "The cell it hangs from (`row`, `col`) comes with the size, since dragging a corner moves the "
        "corner.",
        "rotate_object": "Its anchor cell stays.",
    },
)
add_object_methods(computes_methods, model_of=_workbook, placement=CELLS)
add_rendering_methods(computes_methods, model_of=_workbook, placement=CELLS)
