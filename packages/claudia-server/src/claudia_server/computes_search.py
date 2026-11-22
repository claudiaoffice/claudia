"""Search and replace in a workbook (E6.20, D284-D286): computes' part of the search methods.

What is shared by every app lives in :mod:`claudia_server.search_methods`; this is what a workbook brings: its kinds
of text, its scope (a sheet, and a range on it, or a slide), a place as ``{sheet, row, col}`` or, for the words of an
object on a slide, ``{slide, object, source}`` (CODE-18, UX-72) and who holds a cell or an object.
"""

from __future__ import annotations

from claudia_computes.model import MAX_COLS, MAX_ROWS
from claudia_computes.refs import SheetId
from claudia_computes.region import CellRegion
from claudia_computes.search import (
    EXTRA_PARTS,
    KINDS,
    cell_of,
    place_of,
    plan_replacement,
    replace_command,
    scan_workbook,
)
from claudia_search import Location

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .search_methods import SearchApp
from .search_methods import add_search_methods as _add

MAX_REPLACED_CELLS = 10_000  # cells one replacement may change, as many as one ``set_cells``

FIND_DOC = """Search and replace, the looking (E6.20). `query` is what a person described: `{mode: "text", text}` (what
        is typed is what is found), `{mode: "builder", parts, conditions, combine}` or `{mode: "pattern", find,
        filter}` (her own pattern); each may carry `match_case`, and the first two `whole` (`none`, `entire` or
        `word`) and, to show what a replacement would do, `replace`. A part is `{what, ...}`: `text`, `any_of`,
        `none_of`, `letter`, `digit`, `space`, `any`, `number`, `start`, `end` or, in a workbook, `cellref`. `kinds`
        is any of `text`, `formulas` and `values` (default `["text"]`): the text people typed (in cells, and the words
        of the text boxes and shapes on slides), formulas as typed, and what cells show that was not typed as text.
        `scope` is `{}` (every sheet and slide), `{sheet}`, `{sheet, range: [r0, c0, r1, c1]}` or `{slide}`.

        Answers `{revision, matches, left_out, counts, total, truncated, timed_out, pattern}`. A match is `{at, kind,
        number, start, end, parts, after, text, excerpt, clipped}`: `at` is the cell, `{sheet, row, col}`, or the
        words of an object on a slide, `{slide, object, source}` (`source` `box` or `label`); `kind` is
        `text`, `formula` or `value`, `number` the match's place among those of its cell, `start`/`end` where it is
        in the cell's text, `parts` what the kept parts matched, `after` what a replacement would make of it (`null`
        for a value, or without one), `text` the stretch of the cell around it, `excerpt` the match inside that and
        `clipped` whether the cell goes on before and after it. `left_out` are cells that look like matches but fail
        a condition, `{at, kind, why}`. `counts` are cells with a match, by kind; `total` all matches, of which at
        most 2000 are listed. `pattern` is `{find, filter, replace}`, the three fields that say the same search as
        text. A search that cannot run, a mistake in the person's pattern, is not an error: it answers `error:
        {message, field, position}` and finds nothing, so that a client can say so while she types. `timed_out` says
        the search stopped after two seconds, before it had seen everything; what it found by then is listed."""

PREVIEW_DOC = """What `search_replace` with the same parameters would do, without doing it: `{revision, changes,
        skipped,
        total, timed_out}`. A change is `{at, kind, before, after}` (`at` the cell, `{sheet, row, col}`; `kind` is
        `text` or `formula`; at most 2000 are listed, `total` is how many there are); a skipped cell is `{at, kind,
        reason, by}`, the reason being `locked` (`by` holds it), `formula` (the result would no longer be a formula
        that reads) or `too_long`. `leave` lists the matches to keep as `{at, match}`, `match` being a match's
        `number` in its cell or null for all of them. Only text and formulas are ever replaced, whatever `kinds`
        says. `timed_out`: the search stopped after two seconds and the preview is not complete (`search_replace`
        would refuse). A query that cannot run answers `error` as `search_find` does."""

REPLACE_DOC = """Replace what `search_find` finds, with `query.replace` (the same parameters as `search_preview`, which
        shows the effect first). One change in the history, stored as the cells it changes: undoing it restores them
        all. Cells held by somebody else are skipped and named in `skipped` (`{at, kind, reason, by}`), never refused
        as a whole. Answers `{revision, replaced, skipped}`, `replaced` being the number of cells changed (nothing
        changing is not an error and leaves no entry in the history). `command_error` for a query that cannot run,
        has nothing to replace with or did not finish within two seconds (nothing is replaced then); `bad_request`
        when more than 10000 cells would change."""


def add_search_methods(table: MethodTable, *, workbook) -> None:
    """Add the three search methods to computes' method table; ``workbook`` is the document's model, or refuses."""

    def plan(ctx, compiled, kinds, where, leave, deadline):
        tabs, area = where
        return plan_replacement(
            workbook(ctx),
            compiled,
            kinds=kinds,
            tabs=tabs,
            area=area,
            leave=leave,
            held=_holder(ctx, workbook(ctx)),
            max_length=ctx.limits.max_text,
            deadline=deadline,
        )

    def scan(model, compiled, kinds, where, deadline):
        tabs, area = where
        return scan_workbook(model, compiled, kinds=kinds, tabs=tabs, area=area, deadline=deadline)

    _add(
        table,
        SearchApp(
            kinds=KINDS,
            parts=EXTRA_PARTS,
            model=workbook,
            scope=lambda ctx, scope, method: _search_scope(ctx, scope, method, workbook),
            place=_place,
            scan=scan,
            plan=plan,
            command=replace_command,
            too_many=lambda count, limit: msg(
                "search_replace: that would change {count} cells, at most {limit} at a time: narrow the search",
                count=count,
                limit=limit,
            ),
            bad_place=lambda: msg(
                "leave: each is {at, match}, at being a cell {sheet, row, col} or the words of an object "
                "{slide, object, source}, and match a number or null"
            ),
            max_replaced=lambda: MAX_REPLACED_CELLS,
            find_doc=FIND_DOC,
            preview_doc=PREVIEW_DOC,
            replace_doc=REPLACE_DOC,
        ),
    )


def _place(at) -> Location:
    place = place_of(at)
    if "sheet" in place and (place["row"] >= MAX_ROWS or place["col"] >= MAX_COLS):
        raise ValueError("outside any sheet")
    return place


def _search_scope(
    ctx: Context, scope: dict | None, method: str, workbook
) -> tuple[list[str] | None, tuple[int, int, int, int] | None]:
    """``(tabs, area)``: no scope is every sheet and slide, ``{"sheet": id}`` one sheet, and with ``"range": [r0, c0,
    r1, c1]`` a selection on it; ``{"slide": id}`` one slide (UX-72)."""
    scope = scope or {}
    if set(scope) == {"slide"}:
        if scope["slide"] not in workbook(ctx).slides:
            raise RequestError("command_error", msg("unknown slide {slide!r}", slide=scope["slide"]))
        return [scope["slide"]], None
    if set(scope) - {"sheet", "range"}:
        raise RequestError(
            "bad_request", msg("{method}: a scope has a sheet and, on it, a range, or a slide", method=method)
        )
    sheet, area = scope.get("sheet"), scope.get("range")
    if area is not None and sheet is None:
        raise RequestError("bad_request", msg("{method}: a range is on a sheet: say which", method=method))
    if sheet is None:
        return None, None
    if not isinstance(sheet, str):
        raise RequestError("bad_request", msg("{method}: a sheet is named by its id", method=method))
    workbook(ctx).sheet(SheetId(sheet))  # (command_error for a sheet this document does not have)
    if area is None:
        return [sheet], None
    ok = isinstance(area, list) and len(area) == 4 and all(isinstance(n, int) and not isinstance(n, bool) for n in area)
    if not ok or not (0 <= area[0] <= area[2] < MAX_ROWS and 0 <= area[1] <= area[3] < MAX_COLS):
        raise RequestError(
            "bad_request", msg("{method}: a range is [first row, first column, last row, last column]", method=method)
        )
    return [sheet], (area[0], area[1], area[2], area[3])


def _holder(ctx: Context, model):
    """Who holds a cell or an object, when it is somebody else: asks the document's locks once per sheet, and per
    object for the words of one on a slide."""
    locks: dict[str, list] = {}

    def held(at: Location) -> str | None:
        if "object" in at:
            found = ctx.document.presence.conflicts(ctx.user, list(model.selection_of(at["object"])))
            return found[0][0] if found else None
        sheet, row, col = cell_of(at)
        if sheet not in locks:
            whole = CellRegion.of(SheetId(sheet), 0, 0, MAX_ROWS - 1, MAX_COLS - 1)
            locks[sheet] = ctx.document.presence.conflicts(ctx.user, [whole])
        here = CellRegion.of(SheetId(sheet), row, col, row, col)
        return next((owner for owner, region in locks[sheet] if region.overlaps(here)), None)

    return held
