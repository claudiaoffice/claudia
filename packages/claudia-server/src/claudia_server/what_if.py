"""The what-if desk (D236, D263, D1308): try something on a private copy of the document, through the app's own methods,
look at it with the views the app already has, and carry it out as one step if nobody has worked on the same places since.

One :class:`WhatIfDesk` per hosted document keeps what people are trying. It is **private**: a token belongs to the person
who started it, and nobody else can read, change, commit or drop it. Limits: :data:`MAX_PER_PERSON` for a person,
:data:`MAX_PER_DOCUMENT` for the document, :data:`IDLE_SECONDS` without use, and everything of a person goes when their last
window closes. A what-if is built when first asked for, never in advance (building the copy costs the size of the state).

A write on the copy is a request of the app's own method table, answered with the person's own rights (the rule of
D251), with the copy in the place of the live document: what a what-if does it does exactly as the document would. What
cannot be tried is what is not an edit of the content (history, locks, people, chat): :data:`NOT_TRIED`.
"""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Any
from weakref import WeakKeyDictionary

from claudia_core import Command, Document, KernelError, ProposalOutdated, Revision, WhatIf

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .replay import VIEW_READS, PastDocument

MAX_PER_PERSON = 3
MAX_PER_DOCUMENT = 12
IDLE_SECONDS = 15 * 60.0

#: Requests that change the document's history, locks, people or chat, not its content: they are not tried on a copy.
NOT_TRIED = frozenset(
    {
        "answer_restore",
        "chat",
        "discard_side_history",
        "lock",
        "unlock",
        "propose_restore",
        "propose_restore_step",
        "propose_switch",
        "withdraw_restore",
        "set_restore_policy",
        "set_role",
        "redact",
        "redo",
        "undo",
        "save_checkpoint",
        "what_if_start",
        "what_if_apply",
        "what_if_commit",
        "what_if_drop",
    }
)

#: What a person may say a step was made by when they carry out a proposal.
VIA = frozenset({"ai"})


@dataclass
class _Kept:
    owner: str
    what_if: WhatIf
    used: float


class WhatIfDesk:
    """The what-ifs people are trying on one document."""

    def __init__(self) -> None:
        self._kept: OrderedDict[str, _Kept] = OrderedDict()

    def _expire(self, now: float) -> None:
        for token in [t for t, kept in self._kept.items() if now - kept.used > IDLE_SECONDS]:
            del self._kept[token]

    def start(self, document: Document, owner: str, at: Revision | None) -> tuple[str, WhatIf]:
        """A new what-if of ``owner``'s; ``unavailable`` when they (or the document) have too many."""
        now = time.monotonic()
        self._expire(now)
        mine = sum(1 for kept in self._kept.values() if kept.owner == owner)
        if mine >= MAX_PER_PERSON or len(self._kept) >= MAX_PER_DOCUMENT:
            raise RequestError(
                "unavailable", msg("too many previews are open: finish or drop one before starting another")
            )
        try:
            idea = document.what_if(at, author=owner)
        except KernelError as exc:
            raise RequestError("command_error", str(exc)) from exc
        token = secrets.token_urlsafe(9)
        self._kept[token] = _Kept(owner, idea, now)
        return token, idea

    def get(self, owner: str, token: str) -> WhatIf:
        """``owner``'s what-if ``token``; ``command_error`` when there is none of theirs (nobody else's is ever told)."""
        now = time.monotonic()
        self._expire(now)
        kept = self._kept.get(token)
        if kept is None or kept.owner != owner:
            raise RequestError("command_error", msg("this preview is gone: start it again"))
        kept.used = now
        return kept.what_if

    def drop(self, owner: str, token: str) -> None:
        """End ``owner``'s what-if ``token``."""
        self.get(owner, token)
        del self._kept[token]

    def drop_person(self, owner: str) -> None:
        """End everything ``owner`` is trying."""
        for token in [t for t, kept in self._kept.items() if kept.owner == owner]:
            del self._kept[token]


_desks: WeakKeyDictionary[Document, WhatIfDesk] = WeakKeyDictionary()


def desk_of(document: Document) -> WhatIfDesk:
    """The desk of ``document``, made when first needed."""
    return _desks.setdefault(document, WhatIfDesk())


def drop_person(document: Document, owner: str) -> None:
    """End everything ``owner`` is trying on ``document`` (their last window closed)."""
    desk = _desks.get(document)
    if desk is not None:
        desk.drop_person(owner)


class _Copy(PastDocument):
    """The document as a method sees it while it writes on a what-if: its model and revision are the copy's, and what it
    ``execute``s is done to the copy and remembered by the what-if."""

    def __init__(self, document: Document, idea: WhatIf):
        # its revision is the live step it started from: the copy's own steps are numbered from 1 again, and a view
        # must not take them for steps of the document
        super().__init__(document, idea.base, idea.document.model)  # type: ignore[arg-type]
        self._idea = idea

    def execute(self, command: Command, **_ignored: Any) -> Any:
        """Do ``command`` to the copy. Author, time, base and via are the what-if's own: a person's copy has one author."""
        return self._idea.apply(command)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._idea.document, name)


def add_what_if_methods(table: MethodTable) -> None:
    """Add the what-if requests to an app's method table: they run the app's own methods on the copy."""

    @table.method("what_if_start", "at:revision?")
    def what_if_start(ctx: Context, *, at: Revision | None) -> dict:
        """Start a private what-if of the document as it is now (or after the step `at`): `{token, base}`. Try things
        with `what_if_apply`, look with `as_what_if`, see what would change with `what_if_changes`, carry it out with
        `what_if_commit` or end it with `what_if_drop`. Only the person who started it can use it. `unavailable` when
        they have three already (or the document has twelve); one unused for 15 minutes is dropped."""
        token, idea = desk_of(ctx.document).start(ctx.document, ctx.user, at)
        return {"token": token, "base": None if idea.base is None else idea.base.to_data()}

    @table.method("what_if_apply", "token:str method:str params:dict={}", write=True)
    def what_if_apply(ctx: Context, *, token: str, method: str, params: dict) -> Any:
        """Run one of the app's own write requests on the what-if `token`, as the person's own rights allow, and answer
        what it answers. The document itself does not change. What is not an edit of the content (undo, history, locks,
        chat, people) is `forbidden`."""
        idea = desk_of(ctx.document).get(ctx.user, token)
        if method in NOT_TRIED or method in VIEW_READS:
            raise RequestError("forbidden", msg("{method} cannot be tried on a preview", method=method))
        copy = replace(ctx, document=_Copy(ctx.document, idea), broadcast=lambda _message: None)  # type: ignore[arg-type]
        return table.dispatch(copy, method, params)

    @table.method("as_what_if", "token:str method:str params:dict={}")
    def as_what_if(ctx: Context, *, token: str, method: str, params: dict) -> Any:
        """Answer one read request for the what-if `token`, exactly as without `as_what_if` but for the copy: the views an
        app already has draw it. `method` is one of the requests a view reads with; nothing else can be asked
        (`forbidden`). `command_error` when the what-if is gone."""
        idea = desk_of(ctx.document).get(ctx.user, token)
        if method not in VIEW_READS:
            raise RequestError("forbidden", msg("{method} cannot be asked for a preview", method=method))
        copy = replace(ctx, document=_Copy(ctx.document, idea))  # type: ignore[arg-type]
        return table.dispatch(copy, method, params)

    @table.method("what_if_changes", "token:str")
    def what_if_changes(ctx: Context, *, token: str) -> dict:
        """Where the what-if `token` would change the document: `{regions, count}`, each place once, as the same
        `{kind: cells|text|objects ...}` regions presence uses. What "this would change" is drawn from."""
        found = desk_of(ctx.document).get(ctx.user, token).changes()
        return {"regions": [region.to_data() for region in found], "count": len(found)}

    @table.method("what_if_commit", "token:str via:str?", write=True)
    def what_if_commit(ctx: Context, *, token: str, via: str | None) -> dict:
        """Carry out the what-if `token` on the document as one step by the person (one undo step); `via` (`"ai"`) says
        what it came from. `{applied: true, revision}` when done, and the what-if is over. When somebody has worked on
        the places it touches since, nothing changes and the answer is `{applied: false, reason, conflicts}` with those
        places; the what-if is kept, to look at or drop. Never rebased."""
        if via is not None and via not in VIA:
            raise RequestError("bad_request", msg("via must be one of {allowed}", allowed=", ".join(sorted(VIA))))
        desk = desk_of(ctx.document)
        idea = desk.get(ctx.user, token)
        try:
            applied = ctx.document.apply_proposal(idea.proposal(), author=ctx.user, via=via)
        except ProposalOutdated as exc:
            reason = msg("the document has changed where this preview acts since it was made")
            return {"applied": False, "reason": reason, "conflicts": [r.to_data() for r in exc.conflicts]}
        desk.drop(ctx.user, token)
        return {"applied": True, "revision": applied.revision.to_data()}

    @table.method("what_if_drop", "token:str", write=False)
    def what_if_drop(ctx: Context, *, token: str) -> dict:
        """End the what-if `token`. `command_error` when it is gone already."""
        desk_of(ctx.document).drop(ctx.user, token)
        return {"dropped": True}
