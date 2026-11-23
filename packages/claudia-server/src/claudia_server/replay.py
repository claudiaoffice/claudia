"""Replaying the history (D551): the read requests of a view, answered for the document as it was after one step.

The three apps already show a document from the answers to a handful of read requests (`slides`, `slide`, `cells`,
`paragraphs`, `objects`, `styles`, ...). To show the past, a client asks the very same requests through ``as_of``, and
the view it already has draws the answers. Nothing of the live document is touched: the request runs against a scratch
model rebuilt at that step (:meth:`claudia_core.Document.materialize`), kept for a short while because a view asks a
dozen things at once and a person who turns the wheel asks for the next step a moment later.

Only what a view reads with can be asked, named in :data:`VIEW_READS`: a method not marked as writing is still not for a
look (`delete_document`, `change_password`, `leave` and `new_recovery_key` are not marked, and must stay out of reach).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import replace
from typing import Any
from weakref import WeakKeyDictionary

from claudia_core import Document, DocumentModel, KernelError, ObjectModel, Revision

from .i18n import message_of, msg
from .planned import planned_state
from .protocol import Context, MethodTable, RequestError

#: The requests a view reads the document with, the same in every app; a replay may ask these, and nothing else.
VIEW_READS = frozenset(
    {
        # the whole document as plain data, and what every app's frame reads
        "snapshot",
        "log",
        "checkpoints",
        "language",
        "palette",
        "styles",
        "style_model",
        "style_uses",
        "images",
        "containers",
        "container_types",
        "shapes",
        "print_setup",
        # creates
        "slides",
        "slide",
        # computes
        "sheets",
        "tabs",
        "cells",
        "sizes",
        "diagrams",
        "chart_figure",
        "names",
        "number_formats",
        "cell_styles",
        "cell_style_at",
        "outcome_table",
        "random_state",
        "objects",
        # composes
        "paragraphs",
        "page",
        "look",
        "suggestions",
    }
)

#: How many past states are kept, and for how long: a view's dozen requests of one step all find the one rebuilt state.
KEPT_STATES = 6
KEPT_SECONDS = 30.0

_kept: WeakKeyDictionary[Document, OrderedDict[str, tuple[float, DocumentModel]]] = WeakKeyDictionary()


def state_at(document: Document, revision: Revision) -> DocumentModel:
    """The document's state after ``revision``, rebuilt once and kept for a moment. ``KernelError`` for a revision the
    document does not have."""
    if not document.log.has(revision):
        raise KernelError(f"there is no revision {revision}")
    now = time.monotonic()
    states = _kept.setdefault(document, OrderedDict())
    for key in [k for k, (at, _m) in states.items() if now - at > KEPT_SECONDS]:
        del states[key]
    key = str(revision)
    if key in states:
        states.move_to_end(key)
        return states[key][1]
    model = document.materialize(revision)
    states[key] = (now, model)
    while len(states) > KEPT_STATES:
        states.popitem(last=False)
    return model


class PastDocument:
    """The document as a request sees it while it is answered for an earlier step: its model and revision are the
    step's; everything else (the log, the people, the history) is the live document's."""

    def __init__(self, document: Document, revision: Revision, model: DocumentModel):
        self._document = document
        self.model = model
        self.revision = revision

    def __getattr__(self, name: str) -> Any:
        return getattr(self._document, name)


def add_replay_methods(table: MethodTable) -> None:
    """Add ``as_of`` and ``as_planned`` to an app's method table, answering from that table."""

    @table.method("as_of", "revision:revision method:str params:dict={}", reads="history")
    def as_of(ctx: Context, *, revision: Revision, method: str, params: dict) -> Any:
        """Answer one read request for the document as it was after the step `revision` (D551), so that the view an app
        already has can show the past: `method` is one of the requests a view reads with (`slides`, `slide`, `cells`,
        `paragraphs`, `objects`, `styles`, `snapshot`, `log` ...) and `params` its own, exactly as without `as_of`.
        `log` ends at that step. Nothing else can be asked this way (`forbidden`), and nothing changes. `command_error`
        for a revision the document does not have."""
        if method not in VIEW_READS:
            raise RequestError("forbidden", msg("{method} cannot be asked for an earlier step", method=method))
        try:
            model = state_at(ctx.document, revision)
        except KernelError as exc:
            raise RequestError("command_error", message_of(exc)) from exc
        past = replace(ctx, document=PastDocument(ctx.document, revision, model))  # type: ignore[arg-type]
        return table.dispatch(past, method, params)

    @table.method("as_planned", "plan:str method:str params:dict={}", reads="history")
    def as_planned(ctx: Context, *, plan: str, method: str, params: dict) -> Any:
        """Answer one read request for the document as a redaction would leave it (D721): `plan` is the token
        `redaction_plan` gave, `method` and `params` as for `as_of`. What the preview of a redaction is drawn with.
        Nothing changes. `command_error` once the plan is no longer kept: ask for it again."""
        if method not in VIEW_READS:
            raise RequestError("forbidden", msg("{method} cannot be asked for an earlier step", method=method))
        model = planned_state(ctx.document, plan)
        if model is None:
            raise RequestError("command_error", msg("this preview is no longer kept; work the redaction out again"))
        past = replace(ctx, document=PastDocument(ctx.document, ctx.document.revision, model))  # type: ignore[arg-type]
        return table.dispatch(past, method, params)

    add_thing_history_method(table)
    add_changes_since_method(table)


#: The most places `changes_since` names; a document changed in more places than this is shown tinted up to here.
MAX_CHANGES = 500


def add_changes_since_method(table: MethodTable) -> None:
    """Add ``changes_since`` to an app's method table."""

    @table.method("changes_since", "revision:revision", reads="history")
    def changes_since(ctx: Context, *, revision: Revision) -> dict:
        """Where the document has changed after the step `revision` (D553): `{regions, truncated}`, each place once, in
        the order it was first changed, as the same `{kind: cells|text|objects ...}` regions presence uses. What the
        view of an earlier step tints under "Show differences from now"; `truncated` is true if there were more places
        than the first 500. `command_error` for a step that is not on the line the document is on."""
        try:
            found = ctx.document.changes_since(revision, MAX_CHANGES)
        except KernelError as exc:
            raise RequestError("command_error", message_of(exc)) from exc
        return {"regions": [r.to_data() for r in found.regions], "truncated": found.truncated}


def add_thing_history_method(table: MethodTable) -> None:
    """Add ``thing_last_seen`` to an app's method table."""

    @table.method("thing_last_seen", "id:str", reads="history")
    def thing_last_seen(ctx: Context, *, id: str) -> dict:  # noqa: A002 - the wire name
        """Where a thing (an object, slide or sheet, by id) is in the history of the line the document is on
        (D551): `{present, revision}`. `present` is whether it is there now; `revision` is the last step after which it
        was, `null` if it never was. A tag in the chat to something deleted since takes a replay there."""
        model = ctx.document.model
        if not isinstance(model, ObjectModel):
            raise RequestError("command_error", msg("this document has nothing that can be named"))
        seen = ctx.document.last_seen(lambda m: isinstance(m, ObjectModel) and m.has_thing(id))
        return {"present": model.has_thing(id), "revision": None if seen is None else seen.to_data()}
