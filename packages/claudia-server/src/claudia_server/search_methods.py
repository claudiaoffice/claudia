"""Search and replace for every app (E5.15, D284-D289): ``search_find``, ``search_preview`` and ``search_replace``.

The search itself is ``claudia_search``'s, on the ``regex`` package: every pattern runs against one deadline per
request (:data:`SEARCH_SECONDS`), so a pattern that backtracks without end stops there instead of holding up every
document on the server (SEC-18). A place in a document travels as ``at``, the app's own small mapping of plain values
(CODE-18): every answer names its matches, changes and skipped texts that way, and ``leave`` sends the same ``at``
back.

What differs between the apps is a :class:`SearchApp`: which kinds of text there are, how a scope is read, what the
texts are, and how a replacement is made and written. Everything else, the wire format, the limits, the deadline and
the errors, is here once.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from claudia_core import Command
from claudia_search import CompiledSearch, Location, Plan, Query, Scan, SearchError

from .i18n import msg
from .protocol import Context, MethodTable, RequestError

SEARCH_SECONDS = 2.0  # how long one request may search (D284); then it says it stopped
MAX_PREVIEWED = 2_000  # changes a preview lists (it says how many there are in all)
MAX_LEFT = 10_000  # matches a person may leave alone in one request


@dataclass(frozen=True)
class SearchApp:
    """What an app brings to the three search methods.

    ``scope`` reads the ``scope`` a client sent into whatever ``scan``/``plan`` take (and refuses it with a
    ``RequestError``); ``place`` checks one ``at`` a client sent back and returns it in its canonical form
    (``ValueError`` if it is not a place of this app); ``scan`` and ``plan`` run on the app's model; ``command``
    turns a plan into the one command that makes it.
    ``too_many`` and ``bad_place`` are the app's own sentences, in its own words for what a place is."""

    kinds: tuple[str, ...]
    parts: Mapping[str, str]
    model: Callable[[Context], Any]
    scope: Callable[[Context, dict | None, str], Any]
    place: Callable[[Any], Location]
    scan: Callable[[Any, CompiledSearch, tuple[str, ...], Any, float], Scan]
    plan: Callable[[Context, CompiledSearch, tuple[str, ...], Any, list, float], Plan]
    command: Callable[[Any, Plan, str], Command | None]
    too_many: Callable[[int, int], str]
    bad_place: Callable[[], str]
    max_replaced: Callable[[], int]  # read when a replacement is asked for, so a test can lower it
    find_doc: str
    preview_doc: str
    replace_doc: str


def add_search_methods(table: MethodTable, app: SearchApp) -> None:
    """Add the three search methods to an app's method table."""

    def _search_find(ctx, *, query, kinds, scope):
        chosen, where = _kinds_of(app, kinds, "search_find"), app.scope(ctx, scope, "search_find")
        try:
            compiled = _search_of(app, query)
        except SearchError as error:
            return _no_search(app, error, {"revision": _rev(ctx)})
        found = app.scan(app.model(ctx), compiled, chosen, where, _deadline())
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

    def _search_preview(ctx, *, query, kinds, scope, leave):
        try:
            made = _plan(app, ctx, query, kinds, scope, leave, "search_preview")
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

    def _search_replace(ctx, *, query, kinds, scope, leave, base):
        made = _plan(app, ctx, query, kinds, scope, leave, "search_replace")
        if made.timed_out:
            raise RequestError(
                "command_error",
                msg(
                    "search_replace: the search took longer than {seconds} seconds, so nothing was replaced: narrow it",
                    seconds=int(SEARCH_SECONDS),
                ),
            )
        if len(made.changes) > app.max_replaced():
            raise RequestError("bad_request", app.too_many(len(made.changes), app.max_replaced()))
        skipped = [skip.to_data() for skip in made.skipped]
        command = app.command(app.model(ctx), made, ctx.user)
        if command is None:
            return {"revision": _rev(ctx), "replaced": 0, "skipped": skipped}
        applied = ctx.document.execute(command, author=ctx.user, base=base)
        return {"revision": applied.revision.to_data(), "replaced": len(made.changes), "skipped": skipped}

    # The documentation of a method is the one of its function; each app words its own (what a place is, what kinds
    # there are), so it is set here and not written as a docstring.
    _search_find.__doc__, _search_preview.__doc__, _search_replace.__doc__ = (
        app.find_doc,
        app.preview_doc,
        app.replace_doc,
    )
    table.method("search_find", "query:dict kinds:list? scope:dict?")(_search_find)
    table.method("search_preview", "query:dict kinds:list? scope:dict? leave:list?")(_search_preview)
    table.method("search_replace", "query:dict kinds:list? scope:dict? leave:list? base:revision?", write=True)(
        _search_replace
    )


# ------------------------------------------------------------------------------------------------- what was sent
def _deadline() -> float:
    return time.monotonic() + SEARCH_SECONDS


def _rev(ctx: Context) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _search_of(app: SearchApp, raw: dict) -> CompiledSearch:
    """The compiled search of a query as a client sends it, with the app's own parts; ``SearchError`` if not."""
    return Query.from_data(raw).compile(app.parts)


def _kinds_of(app: SearchApp, kinds: list | None, method: str) -> tuple[str, ...]:
    chosen = [app.kinds[0]] if kinds is None else kinds
    if not chosen or not all(isinstance(k, str) and k in app.kinds for k in chosen):
        raise RequestError(
            "bad_request", msg("{method}: kinds is a list of {kinds}", method=method, kinds=", ".join(app.kinds))
        )
    return tuple(k for k in app.kinds if k in chosen)


def _no_search(app: SearchApp, error: SearchError, more: dict | None = None) -> dict:
    """What a search that cannot run answers: the mistake, with where it is, and nothing found."""
    return {
        "error": {"message": error.message, "field": error.field, "position": error.position},
        "matches": [],
        "left_out": [],
        "counts": dict.fromkeys(app.kinds, 0),
        "total": 0,
        "truncated": False,
        "timed_out": False,
        **(more or {}),
    }


def _left(app: SearchApp, items: list | None) -> list[tuple[Location, int | None, str | None]]:
    """The matches a person wants to keep, as ``(at, number, said)`` (``number`` ``None``: every match at that place;
    ``said`` what the match said when she saw it, if the client sent it)."""
    if items is not None and len(items) > MAX_LEFT:
        raise RequestError("bad_request", msg("leave: at most {limit} at a time", limit=MAX_LEFT))
    leave: list[tuple[Location, int | None, str | None]] = []
    for item in items or []:
        try:
            if not isinstance(item, dict) or not {"at", "match"} <= set(item) <= {"at", "match", "said"}:
                raise ValueError
            at = app.place(item["at"])
        except ValueError:
            raise RequestError("bad_request", app.bad_place()) from None
        match, said = item["match"], item.get("said")
        if match is not None and (isinstance(match, bool) or not isinstance(match, int) or match < 0):
            raise RequestError(
                "bad_request", msg("leave: match is the number of a match at that place, or null for all")
            )
        if said is not None and not isinstance(said, str):
            raise RequestError("bad_request", msg("leave: said is the text the match had when it was shown"))
        leave.append((at, match, said))
    return leave


def _plan(
    app: SearchApp, ctx: Context, query: dict, kinds: list | None, scope: dict | None, leave: list | None, method: str
) -> Plan:
    chosen, where = _kinds_of(app, kinds, method), app.scope(ctx, scope, method)
    compiled = _search_of(app, query)
    return app.plan(ctx, compiled, chosen, where, _left(app, leave), _deadline())
