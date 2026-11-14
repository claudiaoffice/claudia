"""Search and replace in a workbook (E6.20, D284-D286): ``search_find``, ``search_preview`` and ``search_replace``.

The search itself is ``claudia_search``'s, on the ``regex`` package: every pattern runs against one deadline per
request (:data:`SEARCH_SECONDS`), so a pattern that backtracks without end stops there instead of holding up every
document on the server (SEC-18). A place in a workbook travels as ``at`` = ``{sheet, row, col}`` (CODE-18): every
answer names its matches, changes and skipped cells that way, and ``leave`` sends the same ``at`` back.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from claudia_computes import WorkbookModel
from claudia_computes.model import MAX_COLS, MAX_ROWS
from claudia_computes.refs import SheetId
from claudia_computes.region import CellRegion
from claudia_computes.search import (
    EXTRA_PARTS,
    KINDS,
    cell_of,
    plan_replacement,
    replace_command,
    scan_workbook,
)
from claudia_search import CompiledSearch, Location, Plan, Query, SearchError

from .i18n import msg
from .protocol import Context, MethodTable, RequestError

SEARCH_SECONDS = 2.0  # how long one request may search (D284); then it says it stopped
MAX_REPLACED_CELLS = 10_000  # cells one replacement may change, as many as one ``set_cells``
MAX_PREVIEWED = 2_000  # changes a preview lists (it says how many there are in all)
MAX_LEFT = 10_000  # matches a person may leave alone in one request


def add_search_methods(table: MethodTable, *, workbook: Callable[[Context], WorkbookModel]) -> None:
    """Add the three search methods to computes' method table; ``workbook`` is the document's model, or refuses."""

    @table.method("search_find", "query:dict kinds:list? scope:dict?")
    def _search_find(ctx, *, query, kinds, scope):
        """Search and replace, the looking (E6.20). `query` is what a person described: `{mode: "text", text}` (what
        is typed is what is found), `{mode: "builder", parts, conditions, combine}` or `{mode: "pattern", find,
        filter}` (her own pattern); each may carry `match_case`, and the first two `whole` (`none`, `entire` or
        `word`) and, to show what a replacement would do, `replace`. A part is `{what, ...}`: `text`, `any_of`,
        `none_of`, `letter`, `digit`, `space`, `any`, `number`, `start`, `end` or, in a workbook, `cellref`. `kinds`
        is any of `text`, `formulas` and `values` (default `["text"]`): the text people typed, formulas as typed, and
        what cells show that was not typed as text. `scope` is `{}` (every sheet), `{sheet}` or `{sheet, range: [r0,
        c0, r1, c1]}`.

        Answers `{revision, matches, left_out, counts, total, truncated, timed_out, pattern}`. A match is `{at, kind,
        number, start, end, parts, after, text, excerpt, clipped}`: `at` is the cell, `{sheet, row, col}`; `kind` is
        `text`, `formula` or `value`, `number` the match's place among those of its cell, `start`/`end` where it is
        in the cell's text, `parts` what the kept parts matched, `after` what a replacement would make of it (`null`
        for a value, or without one), `text` the stretch of the cell around it, `excerpt` the match inside that and
        `clipped` whether the cell goes on before and after it. `left_out` are cells that look like matches but fail
        a condition, `{at, kind, why}`. `counts` are cells with a match, by kind; `total` all matches, of which at
        most 2000 are listed. `pattern` is `{find, filter, replace}`, the three fields that say the same search as
        text. A search that cannot run, a mistake in the person's pattern, is not an error: it answers `error:
        {message, field, position}` and finds nothing, so that a client can say so while she types. `timed_out` says
        the search stopped after two seconds, before it had seen everything; what it found by then is listed."""
        chosen, (sheets, area) = _kinds_of(kinds, "search_find"), _search_scope(ctx, scope, "search_find", workbook)
        try:
            compiled = _search_of(query)
        except SearchError as error:
            return _no_search(error, {"revision": _rev(ctx)})
        found = scan_workbook(workbook(ctx), compiled, kinds=chosen, sheets=sheets, area=area, deadline=_deadline())
        return {
            "revision": _rev(ctx),
            "matches": [hit.to_data() for hit in found.matches],
            "left_out": [item.to_data() for item in found.left_out],
            "counts": found.counts,
            "total": found.total,
            "truncated": found.truncated,
            "timed_out": found.timed_out,
            "pattern": compiled.pattern_text(),
        }

    @table.method("search_preview", "query:dict kinds:list? scope:dict? leave:list?")
    def _search_preview(ctx, *, query, kinds, scope, leave):
        """What `search_replace` with the same parameters would do, without doing it: `{revision, changes, skipped,
        total, timed_out}`. A change is `{at, kind, before, after}` (`at` the cell, `{sheet, row, col}`; `kind` is
        `text` or `formula`; at most 2000 are listed, `total` is how many there are); a skipped cell is `{at, kind,
        reason, by}`, the reason being `locked` (`by` holds it), `formula` (the result would no longer be a formula
        that reads) or `too_long`. `leave` lists the matches to keep as `{at, match}`, `match` being a match's
        `number` in its cell or null for all of them. Only text and formulas are ever replaced, whatever `kinds`
        says. `timed_out`: the search stopped after two seconds and the preview is not complete (`search_replace`
        would refuse). A query that cannot run answers `error` as `search_find` does."""
        try:
            made = _plan(ctx, query, kinds, scope, leave, "search_preview", workbook)
        except SearchError as error:
            return {
                "revision": _rev(ctx),
                "error": {"message": error.message, "field": error.field, "position": error.position},
            }
        return {
            "revision": _rev(ctx),
            "changes": [change.to_data() for change in made.changes[:MAX_PREVIEWED]],
            "skipped": [skip.to_data() for skip in made.skipped],
            "total": len(made.changes),
            "timed_out": made.timed_out,
        }

    @table.method("search_replace", "query:dict kinds:list? scope:dict? leave:list? base:revision?", write=True)
    def _search_replace(ctx, *, query, kinds, scope, leave, base):
        """Replace what `search_find` finds, with `query.replace` (the same parameters as `search_preview`, which
        shows the effect first). One change in the history, stored as the cells it changes: undoing it restores them
        all. Cells held by somebody else are skipped and named in `skipped` (`{at, kind, reason, by}`), never refused
        as a whole. Answers `{revision, replaced, skipped}`, `replaced` being the number of cells changed (nothing
        changing is not an error and leaves no entry in the history). `command_error` for a query that cannot run,
        has nothing to replace with or did not finish within two seconds (nothing is replaced then); `bad_request`
        when more than 10000 cells would change."""
        made = _plan(ctx, query, kinds, scope, leave, "search_replace", workbook)
        if made.timed_out:
            raise RequestError(
                "command_error",
                msg(
                    "search_replace: the search took longer than {seconds} seconds, so nothing was replaced: narrow it",
                    seconds=int(SEARCH_SECONDS),
                ),
            )
        if len(made.changes) > MAX_REPLACED_CELLS:
            raise RequestError(
                "bad_request",
                msg(
                    "search_replace: that would change {count} cells, at most {limit} at a time: narrow the search",
                    count=len(made.changes),
                    limit=MAX_REPLACED_CELLS,
                ),
            )
        skipped = [skip.to_data() for skip in made.skipped]
        command = replace_command(made)
        if command is None:
            return {"revision": _rev(ctx), "replaced": 0, "skipped": skipped}
        applied = ctx.document.execute(command, author=ctx.user, base=base)
        return {"revision": applied.revision.to_data(), "replaced": len(made.changes), "skipped": skipped}


# ------------------------------------------------------------------------------------------------- what was sent
def _deadline() -> float:
    return time.monotonic() + SEARCH_SECONDS


def _rev(ctx: Context) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _search_of(raw: dict) -> CompiledSearch:
    """The compiled search of a query as a client sends it, with computes' own parts; ``SearchError`` if not."""
    return Query.from_data(raw).compile(EXTRA_PARTS)


def _kinds_of(kinds: list | None, method: str) -> tuple[str, ...]:
    chosen = ["text"] if kinds is None else kinds
    if not chosen or not all(isinstance(k, str) and k in KINDS for k in chosen):
        raise RequestError(
            "bad_request", msg("{method}: kinds is a list of {kinds}", method=method, kinds=", ".join(KINDS))
        )
    return tuple(k for k in KINDS if k in chosen)


def _search_scope(
    ctx: Context, scope: dict | None, method: str, workbook: Callable[[Context], WorkbookModel]
) -> tuple[list[str] | None, tuple[int, int, int, int] | None]:
    """``(sheets, area)``: no scope is every sheet, ``{"sheet": id}`` one sheet, and with ``"range": [r0, c0, r1,
    c1]`` a selection on it."""
    scope = scope or {}
    if set(scope) - {"sheet", "range"}:
        raise RequestError("bad_request", msg("{method}: a scope has a sheet and, on it, a range", method=method))
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


def _left(items: list | None) -> list[tuple[Location, int | None]]:
    """The matches a person wants to keep, as ``(at, number)`` (``number`` ``None``: every match in that cell)."""
    if items is not None and len(items) > MAX_LEFT:
        raise RequestError("bad_request", msg("leave: at most {limit} at a time", limit=MAX_LEFT))
    leave: list[tuple[Location, int | None]] = []
    for item in items or []:
        try:
            if not isinstance(item, dict) or set(item) != {"at", "match"}:
                raise ValueError
            sheet, row, col = cell_of(item["at"])
        except ValueError:
            raise RequestError(
                "bad_request",
                msg("leave: each is {at, match}, at being a cell {sheet, row, col} and match a number or null"),
            ) from None
        if row >= MAX_ROWS or col >= MAX_COLS:
            raise RequestError("bad_request", msg("leave: that cell is outside any sheet"))
        match = item["match"]
        if match is not None and (isinstance(match, bool) or not isinstance(match, int) or match < 0):
            raise RequestError("bad_request", msg("leave: match is the number of a match in the cell, or null for all"))
        leave.append(({"sheet": sheet, "row": row, "col": col}, match))
    return leave


def _plan(
    ctx: Context,
    query: dict,
    kinds: list | None,
    scope: dict | None,
    leave: list | None,
    method: str,
    workbook: Callable[[Context], WorkbookModel],
) -> Plan:
    chosen, (sheets, area) = _kinds_of(kinds, method), _search_scope(ctx, scope, method, workbook)
    compiled = _search_of(query)
    return plan_replacement(
        workbook(ctx),
        compiled,
        kinds=chosen,
        sheets=sheets,
        area=area,
        leave=_left(leave),
        held=_holder(ctx),
        max_length=ctx.limits.max_text,
        deadline=_deadline(),
    )


def _holder(ctx: Context):
    """Who holds a cell, when it is somebody else: asks the document's locks once per sheet."""
    locks: dict[str, list] = {}

    def held(sheet: str, row: int, col: int) -> str | None:
        if sheet not in locks:
            whole = CellRegion.of(SheetId(sheet), 0, 0, MAX_ROWS - 1, MAX_COLS - 1)
            locks[sheet] = ctx.document.presence.conflicts(ctx.user, [whole])
        here = CellRegion.of(SheetId(sheet), row, col, row, col)
        return next((owner for owner, region in locks[sheet] if region.overlaps(here)), None)

    return held
