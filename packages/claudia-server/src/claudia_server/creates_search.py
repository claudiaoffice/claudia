"""Search and replace in a presentation (E10.19, D284-D289): creates' part of the search methods.

What is shared by every app lives in :mod:`claudia_server.search_methods`; this is what a presentation brings: its
kinds of text (the words in text boxes and shapes, speaker notes, descriptions), its scope (every slide, or one),
a place as ``{slide, object, source}`` or ``{slide, source: notes}`` (CODE-18) and who holds an object.
"""

from __future__ import annotations

from claudia_creates import SlideModel
from claudia_creates.search import (
    EXTRA_PARTS,
    KINDS,
    place_of,
    plan_replacement,
    replace_command,
    scan_slides,
    slide_texts,
)

from .i18n import message_of, msg
from .protocol import Context, MethodTable, RequestError
from .search_methods import SearchApp
from .search_methods import add_search_methods as _add

MAX_REPLACED_TEXTS = 10_000  # texts one replacement may change

FIND_DOC = """Search and replace, the looking (E10.19). `query` is what a person described: `{mode: "text", text}` (what
        is typed is what is found), `{mode: "builder", parts, conditions, combine}` or `{mode: "pattern", find,
        filter}` (her own pattern); each may carry `match_case`, and the first two `whole` (`none`, `entire` or
        `word`) and, to show what a replacement would do, `replace`. A part is `{what, ...}`: `text`, `any_of`,
        `none_of`, `letter`, `digit`, `space`, `any`, `number`, `start`, `end` or, in a presentation, `word`. `kinds`
        is any of `text`, `label`, `notes` and `description` (default `["text"]`): the words in text boxes, the words
        in shapes, speaker notes (as written, Markdown marks included) and what an object says to somebody who
        cannot see it. `scope` is `{}` (every slide) or `{slide}` (this slide).

        Answers `{revision, matches, left_out, counts, total, truncated, timed_out, pattern}`. A match is `{at, kind,
        number, start, end, parts, after, text, excerpt, clipped}`: `at` is the place, `{slide, object, source}` for
        an object (`source` being `box`, `label` or `description`) and `{slide, source: "notes"}` for notes; `kind`
        is one of the kinds above, `number` the match's place among those of its text, `start`/`end` where it is in
        that text, `parts` what the kept parts matched, `after` what a replacement would make of it (`null` without
        one), `text` the stretch around it, `excerpt` the match inside that and `clipped` whether the text goes on
        before and after it. `left_out` are texts that look like matches but fail a condition, `{at, kind, why}`.
        `counts` are texts with a match, by kind; `total` all matches, of which at most 2000 are listed. `pattern`
        is `{find, filter, replace}`, the three fields that say the same search as text. A search that cannot run, a
        mistake in the person's pattern, is not an error: it answers `error: {message, field, position}` and finds
        nothing, so that a client can say so while she types. `timed_out` says the search stopped after two
        seconds, before it had seen everything; what it found by then is listed."""

PREVIEW_DOC = """What `search_replace` with the same parameters would do, without doing it: `{revision, changes,
        skipped, total, timed_out}`. A change is `{at, kind, before, after}` (`at` as in `search_find`; at most 2000
        are listed, `total` is how many there are); a skipped text is `{at, kind, reason, by}`, the reason being
        `locked` (`by` has selected the object), `changed` (it was typed into since the person saw it, so the
        numbers of her `leave` no longer fit) or `too_long`. `leave` lists the matches to keep as `{at, match,
        said}`, `match` being a match's `number` in its text or null for all of them, and `said` (optional) what
        that match said when it was shown. `timed_out`: the search stopped after two seconds and the preview is not
        complete (`search_replace` would refuse). A query that cannot run answers `error` as `search_find` does."""

REPLACE_DOC = """Replace what `search_find` finds, with `query.replace` (the same parameters as `search_preview`, which
        shows the effect first). One change in the history: the words around a match keep whoever wrote them, and
        whoever replaces is the author of what is put in. An object somebody else has selected, and a text that was
        typed into since the person looked, are skipped and named in `skipped` (`{at, kind, reason, by}`), never
        refused as a whole; speaker notes are nobody's to hold. Answers `{revision, replaced, skipped}`, `replaced`
        being the number of texts changed (nothing changing is not an error and leaves no entry in the history).
        `command_error` for a query that cannot run, has nothing to replace with or did not finish within two
        seconds (nothing is replaced then); `bad_request` when more than 10000 texts would change."""


def _deck(ctx: Context) -> SlideModel:
    model = ctx.document.model
    if not isinstance(model, SlideModel):
        raise RequestError("command_error", msg("this document is not a presentation"))
    return model


def _scope(ctx: Context, scope: dict | None, method: str) -> dict | None:
    try:
        slide_texts(_deck(ctx), (), scope)  # (reads the scope, and refuses it if it names nothing that exists)
    except ValueError as error:
        raise RequestError("bad_request", msg("{method}: {why}", method=method, why=message_of(error))) from None
    return scope or None


def add_search_methods(table: MethodTable) -> None:
    """Add the three search methods to creates' method table."""

    def plan(ctx, compiled, kinds, where, leave, deadline):
        return plan_replacement(
            _deck(ctx),
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
            model=_deck,
            scope=_scope,
            place=place_of,
            scan=lambda model, compiled, kinds, where, deadline: scan_slides(
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
                "leave: each is {at, match}, at being a place the search listed ({slide, object, source} or "
                "{slide, source}) and match a number or null"
            ),
            max_replaced=lambda: MAX_REPLACED_TEXTS,
            find_doc=FIND_DOC,
            preview_doc=PREVIEW_DOC,
            replace_doc=REPLACE_DOC,
        ),
    )
