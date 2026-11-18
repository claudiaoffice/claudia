"""Search and replace in a text (E9.28, D284-D289): composes' part of the search methods.

What is shared by every app lives in :mod:`claudia_server.search_methods`; this is what a text brings: its kinds of
text (paragraphs by their style, the words and the descriptions of floating objects), its scope (a section or a
selection), a place as ``{block}`` or ``{block, object, source}`` (CODE-18) and who holds a stretch of text.
"""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_composes.search import (
    EXTRA_PARTS,
    KINDS,
    block_of,
    object_of,
    plan_replacement,
    replace_command,
    scan_text,
    table_of,
    text_texts,
)
from claudia_search import Location

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .search_methods import SearchApp
from .search_methods import add_search_methods as _add

MAX_REPLACED_TEXTS = 10_000  # paragraphs and object texts one replacement may change

FIND_DOC = """Search and replace, the looking (E9.28). `query` is what a person described: `{mode: "text", text}` (what
        is typed is what is found), `{mode: "builder", parts, conditions, combine}` or `{mode: "pattern", find,
        filter}` (her own pattern); each may carry `match_case`, and the first two `whole` (`none`, `entire` or
        `word`) and, to show what a replacement would do, `replace`. A part is `{what, ...}`: `text`, `any_of`,
        `none_of`, `letter`, `digit`, `space`, `any`, `number`, `start`, `end` or, in a text, `word`. `kinds` is any of
        `text`, `heading`, `remark`, `object`, `description` and `table` (default `["text"]`): paragraphs in a body
        style, in a title or heading style, in the remark style (or a style based on one of them), the words in an
        object floating over the text (a text box, a shape's label), what an object says to somebody who cannot see
        it, and the words in the boxes of a table (row by row, a box a merge covers has none).
        `scope` is `{}` (the whole text), `{section: paragraph}` (the section that paragraph is in: from its heading
        to the next heading of the same or a higher level) or `{range: {from: {block, offset}, to: {block, offset}}}`
        (a selection).

        Answers `{revision, matches, left_out, counts, total, truncated, timed_out, pattern}`. A match is `{at, kind,
        number, start, end, parts, after, text, excerpt, clipped}`: `at` is the place, `{block}` for a paragraph
        (`{block, offset}` when only the part from `offset` on was searched, a selection's first or last paragraph:
        `start` and `end` count from there), `{block, object, source}` for an object (`block` the paragraph it hangs
        from), `source` being `box`, `label` or `description`, and `{block, table, row, col}` for a box of a table
        (`block` the paragraph its table hangs from; the ids are those `tables` lists); `kind` is one of the kinds
        above, `number` the match's place among those of its text, `start`/`end` where it is in that text,
        `parts` what the kept parts matched, `after` what a replacement would
        make of it (`null` without one), `text` the stretch around it, `excerpt` the match inside that and `clipped`
        whether the text goes on before and after it. `left_out` are texts that look like matches but fail a
        condition, `{at, kind, why}`. `counts` are texts with a match, by kind; `total` all matches, of which at most
        2000 are listed. `pattern` is `{find, filter, replace}`, the three fields that say the same search as text.
        A search that cannot run, a mistake in the person's pattern, is not an error: it answers `error: {message,
        field, position}` and finds nothing, so that a client can say so while she types. `timed_out` says the search
        stopped after two seconds, before it had seen everything; what it found by then is listed."""

PREVIEW_DOC = """What `search_replace` with the same parameters would do, without doing it: `{revision, changes,
        skipped, total, timed_out}`. A change is `{at, kind, before, after}` (`at` as in `search_find`; at most 2000
        are listed, `total` is how many there are); a skipped text is `{at, kind, reason, by}`, the reason being
        `locked` (`by` holds a stretch of it that a match lies in, or the object), `changed` (it was typed into
        since the person saw it, so the numbers of her `leave` no longer fit) or `too_long`. `leave` lists the
        matches to keep as `{at, match, said}`, `match` being a match's `number` in its text or null for all of
        them, and `said` (optional) what that match said when it was shown. `timed_out`: the search stopped after
        two seconds and the preview is not complete (`search_replace` would refuse). A query that cannot run answers
        `error` as `search_find` does."""

REPLACE_DOC = """Replace what `search_find` finds, with `query.replace` (the same parameters as `search_preview`, which
        shows the effect first). One change in the history, stored as typing and deleting: the words around a match
        keep whoever wrote them, and whoever replaces is the author of what is put in. A paragraph with a match
        inside a stretch somebody else holds, an object somebody has selected, and a text that was typed into since
        the person looked, are skipped and named in `skipped` (`{at, kind, reason, by}`), never refused as a whole.
        Answers `{revision, replaced, skipped}`, `replaced` being the number of texts changed (nothing changing is not
        an error and leaves no entry in the history). `command_error` for a query that cannot run, has nothing to
        replace with or did not finish within two seconds (nothing is replaced then); `bad_request` when more than
        10000 texts would change."""


def _text(ctx: Context) -> TextModel:
    model = ctx.document.model
    if not isinstance(model, TextModel):
        raise RequestError("command_error", msg("this document is not a text"))
    return model


def _scope(ctx: Context, scope: dict | None, method: str) -> dict | None:
    try:
        text_texts(_text(ctx), (), scope)  # (reads the scope, and refuses it if it names nothing that exists)
    except ValueError as error:
        raise RequestError("bad_request", msg("{method}: {why}", method=method, why=str(error))) from None
    return scope or None


def _place(at) -> Location:
    try:
        block, offset = block_of(at)
    except ValueError:
        try:
            block, object_id, source = object_of(at)
        except ValueError:
            block, table, row, col = table_of(at)
            return {"block": block, "table": table, "row": row, "col": col}
        return {"block": block, "object": object_id, "source": source}
    return {"block": block} if "offset" not in at else {"block": block, "offset": offset}


def add_search_methods(table: MethodTable) -> None:
    """Add the three search methods to composes' method table."""

    def plan(ctx, compiled, kinds, where, leave, deadline):
        return plan_replacement(
            _text(ctx),
            compiled,
            kinds=kinds,
            scope=where,
            leave=leave,
            conflicts=lambda regions: ctx.document.presence.conflicts(ctx.user, regions),
            max_length=ctx.limits.max_text,
            deadline=deadline,
        )

    _add(
        table,
        SearchApp(
            kinds=KINDS,
            parts=EXTRA_PARTS,
            model=_text,
            scope=_scope,
            place=_place,
            scan=lambda model, compiled, kinds, where, deadline: scan_text(
                model, compiled, kinds=kinds, scope=where, deadline=deadline
            ),
            plan=plan,
            command=replace_command,
            too_many=lambda count, limit: msg(
                "search_replace: that would change {count} texts, at most {limit} at a time: narrow the search",
                count=count,
                limit=limit,
            ),
            bad_place=lambda: msg(
                "leave: each is {at, match}, at being a place the search listed ({block}, "
                "{block, object, source} or {block, table, row, col}) and match a number or null"
            ),
            max_replaced=lambda: MAX_REPLACED_TEXTS,
            find_doc=FIND_DOC,
            preview_doc=PREVIEW_DOC,
            replace_doc=REPLACE_DOC,
        ),
    )
