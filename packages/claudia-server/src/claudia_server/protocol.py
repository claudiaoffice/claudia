"""The wire protocol: which requests exist, what they accept, and what they do (E3.1).

Messages are JSON text frames.

    client -> server   {"id": 7, "method": "apply", "params": {"command": {...}, "base": "main:12"}}
    server -> client   {"id": 7, "ok": true,  "result": {"revision": "main:13"}}
                       {"id": 7, "ok": false, "error": {"code": "stale", "message": "..."}}
    server -> client   {"event": "command", "data": {...}}                    pushed, no id

Every request gets exactly one response with the same ``id`` (an integer or a short string chosen by the client).
Events caused by a request are sent *before* its response, so when the response arrives the client has seen the
change.

The method table is the single source of truth: it validates parameters, says who may call what, and is published by
``MethodTable.describe`` (served at ``/api/protocol``) so clients in other languages can be generated or checked
against it (E3.2). The table in this module, ``core_methods``, holds what every app has (documents, undo,
checkpoints, presence, locks, chat); an app takes ``core_methods.extended()`` and adds its own methods and parameter
types. A *command* travels in its stored form (``{"k": kind, "s": schema, "d": data}``), so the protocol never needs
to know what a spreadsheet, a text or a slide is.

Restoring a checkpoint or switching the line moves everybody, so neither happens from a bare request: an owner or
editor *suggests* it (``propose_restore``, ``propose_switch``), and it is carried out once everybody who is
connected now as an owner or editor has agreed (``answer_restore``; ``restore.py`` is the consent itself, E3.7) —
unless the one suggesting it is the only one, in which case it happens at once. Either way the result reaches
connected clients the same way: ``branch`` and ``rebuilt`` events, and the ``stale`` error for an edit that was
written against the line left behind.

This module has no web framework in it, so it is tested without sockets.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from claudia_core import (
    Document,
    KernelError,
    RegionHeld,
    Revision,
    SchemaTooNew,
    StaleEdit,
    UndoConflict,
    UnknownCommand,
)

from .ai_mode import parse_mode
from .auth import (
    Account,
    DeletableDirectory,
    LeavableDirectory,
    RecoverableDirectory,
    RosterDirectory,
    TransferableDirectory,
    UserDirectory,
)
from .help import default_library
from .i18n import localized, msg
from .restore import POLICIES, RestoreCoordinator, RestoreError

if TYPE_CHECKING:
    from claudia_core import Region

PROTOCOL_VERSION = 2
INT_MAX = 2**31 - 1
MAX_LOG = 5000

DEFAULT_LOCALE = "en"
_LOCALE = re.compile(r"[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*")  # a BCP-47-ish tag; loose, since this only picks a catalog


def normalize_locale(raw: object) -> str:
    """The client's own locale (E5.7, D31), as sent in ``hello``: a short tag, or ``DEFAULT_LOCALE`` if ``raw`` is
    missing, not a string, too long to be a tag, or not shaped like one. Never raises: a malformed locale is a reason
    to fall back, not a reason to refuse the connection."""
    if not isinstance(raw, str) or not (2 <= len(raw) <= 35) or not _LOCALE.fullmatch(raw):
        return DEFAULT_LOCALE
    return raw


ERROR_CODES = {
    "bad_request": "malformed message, unknown or missing parameter, wrong type, or over a limit",
    "unknown_method": "no such method",
    "command_error": "the request was understood but rejected (bad index, unknown sheet...); nothing changed",
    "forbidden": "the account may not do this (read-only role)",
    "unauthorized": "missing or wrong credentials",
    "not_found": "no such document",
    "unavailable": "a server limit was reached (too many connections to the document)",
    "sealed": "the document is stored but nobody who holds all its keys has opened it since the server started; "
    "a viewer has to wait (and may try again) until an owner or editor has",
    "locked": "somebody else is working on that part of the document right now; nothing changed",
    "conflict": "undo or redo would overwrite a colleague's later work; nothing changed",
    "stale": "the request was made against a view of the document that is gone (it went back to a checkpoint or "
    "changed line); reload the document and try again; nothing changed",
    "internal": "a server error; the request may or may not have been applied, check the revision",
}

EVENTS = {
    "command": "a command was applied, by anyone: {revision, author, origin (do|undo|redo), time, label, summary}. "
    "State events of the app (the document's own, e.g. cells changed) come just before it",
    "history": "your undo and redo state changed: {author, can_undo, can_redo, undo_label, redo_label}; sent to that "
    "author only",
    "checkpoint": "somebody saved a checkpoint: {number, label, author, marks}",
    "chat": "a chat message: {number, author, to, text, time, at}; only its sender and recipient get one that is not "
    "for everybody",
    "ephemeral": "something that is not stored: {kind: presence|preview|typing|person_left|owner_changed|"
    "document_deleted|..., sender, data}. person_left: {user}; owner_changed: {owner}; document_deleted: {}, and "
    "nothing else will ever be stored or delivered for this document — close and forget it",
    "branch": "the document moved to another line (a checkpoint was restored, or the way back was taken): {old, new, "
    "fork_point}. Everything you hold is stale: call snapshot",
    "rebuilt": "the state was rebuilt from the log (after a restore, a switch or a redaction): call snapshot",
    "redacted": "the content of these revisions was removed: {revisions}",
    "stale": "functions the document uses changed: {functions}; results computed by them are out of date",
    "joined": "somebody connected: {id, user, color}",
    "left": "somebody disconnected: {id, user}; their presence and locks are gone if it was their last connection",
    "restore_proposed": "a suggestion to restore a checkpoint or switch the line is open, or its answers changed "
    "(see `propose_restore`): the proposal, as `answer_restore` returns it",
    "restore_resolved": "the open suggestion closed: {outcome: agreed|declined|withdrawn}. `agreed` is followed by "
    "`branch` and `rebuilt`, same as any restore or switch",
}


class RequestError(Exception):
    """A request failed in a way the client is told about: ``code`` is one of ``ERROR_CODES``.

    ``message`` is English text, or a ``claudia_server.i18n.Message`` (``msg("...")``) that :meth:`to_dict` says
    in the language of the connection it is sent to (E5.7, D322); what the core packages raise stays English.

    ``detail``, when given, is the finer-grained ``code`` of the ``claudia_core`` error this came from (E5.7
    groundwork): ``code`` stays the small, stable wire category a client already branches on (``"locked"``,
    ``"stale"``...), while ``detail`` is what a future translator would use to pick the exact message to render."""

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self, locale: str = DEFAULT_LOCALE) -> dict:
        """The error as sent in a response, its message in ``locale`` (the connection's own, D31)."""
        out = {"code": self.code, "message": localized(self.message, locale)}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


@dataclass(frozen=True)
class Limits:
    """Caps that keep one client from exhausting the server. Apps add their own in their own settings."""

    max_text: int = 32_767  # characters in one text parameter (a chat message, a cell input)
    max_message_bytes: int = 16 * 1024 * 1024
    max_regions: int = 16  # regions one request may show or lock

    def to_dict(self) -> dict:
        """The limits as sent to a client in the welcome."""
        return dict(self.__dict__)


# ----------------------------------------------------------------- parameter types
def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and abs(value) <= INT_MAX


def _int(value: Any, limits: Limits) -> int:
    """integer"""
    if not _is_int(value):
        raise ValueError("must be an integer")
    return value


def _number(value: Any, limits: Limits) -> float:
    """finite number"""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError("must be a finite number")
    return float(value)


def _bool(value: Any, limits: Limits) -> bool:
    """true / false"""
    if not isinstance(value, bool):
        raise ValueError("must be true or false")
    return value


def _str(value: Any, limits: Limits) -> str:
    """string, at most 1000 characters (ids, names)"""
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError("must be a string of at most 1000 characters")
    return value


def _text(value: Any, limits: Limits) -> str:
    """string, at most limits.max_text characters (chat, cell input)"""
    if not isinstance(value, str) or len(value) > limits.max_text:
        raise ValueError(f"must be a string of at most {limits.max_text} characters")
    return value


def _dict(value: Any, limits: Limits) -> dict:
    """object"""
    if not isinstance(value, dict):
        raise ValueError("must be an object")
    return value


def _list(value: Any, limits: Limits) -> list:
    """array"""
    if not isinstance(value, list):
        raise ValueError("must be a list")
    return value


def _any(value: Any, limits: Limits) -> Any:
    """anything"""
    return value


def _revision(value: Any, limits: Limits) -> Revision:
    """a revision as the server writes it: \"line:number\", e.g. \"main:12\" """
    if not isinstance(value, str):
        raise ValueError('must be a revision like "main:12"')
    try:
        return Revision.parse(value)
    except ValueError:
        raise ValueError('must be a revision like "main:12"') from None


def _regions(value: Any, limits: Limits) -> list[dict]:
    """array of regions in the app's wire form (each an object with a kind), at most limits.max_regions"""
    if not isinstance(value, list) or len(value) > limits.max_regions:
        raise ValueError(f"must be a list of at most {limits.max_regions} regions")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("must be a list of region objects")
    return value


@dataclass(frozen=True)
class Param:
    """One parameter of a method."""

    name: str
    kind: str
    required: bool = True
    default: Any = None

    def to_dict(self) -> dict:
        """The parameter as described to client developers."""
        return {"name": self.name, "type": self.kind, "required": self.required, "default": self.default}


def _parse_params(spec: str) -> tuple[Param, ...]:
    """``"label:str? count:int=1"``: name:type, optional ``=json`` default, or ``?`` for default null."""
    params = []
    for token in spec.split():
        name, _, rest = token.partition(":")
        if rest.endswith("?"):
            params.append(Param(name, rest[:-1], required=False, default=None))
        elif "=" in rest:
            kind, _, literal = rest.partition("=")
            params.append(Param(name, kind, required=False, default=json.loads(literal)))
        else:
            params.append(Param(name, rest))
    return tuple(params)


# --------------------------------------------------------------------- method table
@dataclass
class Context:
    """What a method works with: the document, who asks, the limits, and who is connected."""

    document: Document
    account: Account
    limits: Limits
    users: Callable[[], list[str]] = field(default=lambda: [])  # names of the people connected now
    lock_seconds: float = 300.0  # how long a lock lasts without being renewed
    directory: UserDirectory | None = None  # where this document's people are kept, if the server manages them
    doc_id: str = ""
    locale: str = DEFAULT_LOCALE  # the connection's own locale (E5.7, D31); what a method says is said in it
    editors: Callable[[], list[str]] = field(default=lambda: [])  # connected now, and may write (E3.7)
    # The open restore/switch suggestion, if any, and the consent around it (E3.7); a harmless, unattached one by
    # default, for contexts nothing here is asked of.
    restore: RestoreCoordinator = field(
        default_factory=lambda: RestoreCoordinator(lambda record: None, clock=lambda: 0.0)
    )
    broadcast: Callable[[dict], None] = field(default=lambda message: None)  # tell every window of this document
    # Tell the AI of this document how the next request of a person is to be treated (D262); nothing if there is none.
    note_ai_mode: Callable[[str, str | None], None] = field(default=lambda user, mode: None)
    set_locale: Callable[[str], None] = field(default=lambda locale: None)  # change this window's language (D323)

    @property
    def user(self) -> str:
        """The author of what this request changes."""
        return self.account.user


@dataclass(frozen=True)
class Method:
    """One request: its name, parameters, whether it needs a role that may write, and the function."""

    name: str
    params: tuple[Param, ...]
    write: bool
    doc: str
    fn: Callable[..., Any] = field(repr=False)


class MethodTable:
    """The methods and parameter types of a protocol. An app extends a copy (``extended``)."""

    def __init__(self) -> None:
        self._methods: dict[str, Method] = {}
        self._kinds: dict[str, Callable[[Any, Limits], Any]] = {}

    # -- building ---------------------------------------------------------------------
    def method(self, name: str, spec: str = "", *, write: bool = False):
        """Decorator: register ``fn(ctx, **params)`` as method ``name``.

        ``spec`` lists the parameters as ``"name:type name:type=default"``."""

        def register(fn):
            self._methods[name] = Method(name, _parse_params(spec), write, (fn.__doc__ or "").strip(), fn)
            return fn

        return register

    def kind(self, name: str):
        """Decorator: register ``check(value, limits)`` as parameter type ``name``; it returns the value or raises
        ValueError."""

        def register(check):
            self._kinds[name] = check
            return check

        return register

    def extended(self) -> MethodTable:
        """A copy an app can add to without changing this table."""
        copy = MethodTable()
        copy._methods = dict(self._methods)
        copy._kinds = dict(self._kinds)
        return copy

    def names(self) -> set[str]:
        """The names of all methods."""
        return set(self._methods)

    # -- running ----------------------------------------------------------------------
    def bind(self, entry: Method, raw: Any, limits: Limits) -> dict[str, Any]:
        """Validate the request's params against the method's spec and fill in defaults."""
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise RequestError("bad_request", msg("params must be an object"))
        extra = sorted(set(raw) - {p.name for p in entry.params})
        if extra:
            raise RequestError(
                "bad_request", msg("unknown parameter {parameter!r} for {name}", parameter=extra[0], name=entry.name)
            )
        args = {}
        for p in entry.params:
            if p.name not in raw or (raw[p.name] is None and not p.required):
                if p.required:
                    raise RequestError(
                        "bad_request",
                        msg("{method}: missing parameter {parameter!r}", method=entry.name, parameter=p.name),
                    )
                args[p.name] = p.default
                continue
            try:
                args[p.name] = self._kinds[p.kind](raw[p.name], limits)
            except ValueError as exc:
                raise RequestError(
                    "bad_request",
                    msg("{method}: {parameter} {reason}", method=entry.name, parameter=p.name, reason=exc),
                ) from None
        return args

    def dispatch(self, ctx: Context, name: Any, params: Any) -> Any:
        """Run one request and return its JSON-able result. Raises ``RequestError``."""
        if not isinstance(name, str):
            raise RequestError("bad_request", msg("method must be a string"))
        entry = self._methods.get(name)
        if entry is None:
            raise RequestError("unknown_method", msg("no method {name!r}", name=name))
        if entry.write and not ctx.account.can_write:
            raise RequestError("forbidden", msg("{name} needs the editor role", name=name))
        allowed = ctx.account.allowed_methods
        if entry.write and allowed is not None and name not in allowed:
            # SEC-10: the one place every path goes through (the wire, the assistant, a future remote engine).
            raise RequestError("forbidden", msg("{name} is not one of the methods this account may call", name=name))
        args = self.bind(entry, params, ctx.limits)
        try:
            return entry.fn(ctx, **args)
        except RequestError:
            raise
        except StaleEdit as exc:
            raise RequestError("stale", str(exc), detail=exc.code) from exc
        except RegionHeld as exc:  # (and UndoRefused, which is one)
            raise RequestError("locked", str(exc), detail=exc.code) from exc
        except UndoConflict as exc:
            raise RequestError("conflict", str(exc), detail=exc.code) from exc
        except (
            KernelError,
            ValueError,
            LookupError,
        ) as exc:  # a command refuses with ValueError / IndexError / KeyError; only KernelError has a `code`
            raise RequestError("command_error", str(exc), detail=getattr(exc, "code", None)) from exc

    def describe(self, limits: Limits | None = None) -> dict:
        """A machine-readable description of the protocol (served at /api/protocol)."""
        return {
            "protocol": PROTOCOL_VERSION,
            "framing": "JSON text frames; requests {id, method, params}; responses {id, ok, result | error}; "
            "pushed {event, data}",
            "methods": {
                m.name: {"write": m.write, "doc": m.doc, "params": [p.to_dict() for p in m.params]}
                for m in self._methods.values()
            },
            "param_types": {
                name: (check.__doc__ or "defined by the app").strip() for name, check in self._kinds.items()
            },
            "events": EVENTS,
            "errors": ERROR_CODES,
            "limits": (limits or Limits()).to_dict(),
        }


def parse_request(raw: str | bytes, limits: Limits) -> tuple[Any, Any, Any]:
    """``(id, method, params)`` of a request frame; raises ``RequestError`` for a malformed one."""
    if len(raw) > limits.max_message_bytes:
        raise RequestError("bad_request", msg("message too large"))
    try:
        message = json.loads(raw)
    except (ValueError, RecursionError):
        raise RequestError("bad_request", msg("not valid JSON")) from None
    if not isinstance(message, dict):
        raise RequestError("bad_request", msg("a request must be a JSON object"))
    request_id = message.get("id")
    if not (isinstance(request_id, str) and len(request_id) <= 100) and not _is_int(request_id):
        raise RequestError("bad_request", msg("id must be an integer or a short string"))
    return request_id, message.get("method"), message.get("params")


core_methods = MethodTable()
for _name, _check in (
    ("int", _int),
    ("number", _number),
    ("bool", _bool),
    ("str", _str),
    ("text", _text),
    ("dict", _dict),
    ("list", _list),
    ("any", _any),
    ("revision", _revision),
    ("regions", _regions),
):
    core_methods.kind(_name)(_check)


def _regions_of(ctx: Context, items: list[dict]) -> list[Region]:
    try:
        return [ctx.document.model.region_from_data(item) for item in items]
    except (KeyError, TypeError, ValueError, NotImplementedError) as exc:
        raise RequestError(
            "bad_request", msg("not a region this document understands: {reason!r}", reason=exc)
        ) from None


def _checkpoint(info) -> dict:
    return {
        "number": info.number,
        "label": info.label,
        "author": info.author,
        "marks": info.marks.to_data(),
        "entry": info.entry.to_data(),
        "time": info.time,
    }


# -- help (E13.1, E13.3): the same two read-only methods for every app. A topic names the apps it is for itself
# (its ``apps`` front matter), so `_help_search` only has to pass the asking document's own app along; no table of
# which id belongs to which app lives here. Not gated by ``allowed_methods`` (nothing here writes), so the ``ai``
# user gets the same read access as everybody (E13.4).
@core_methods.method("help_search", 'query:str=""')
def _help_search(ctx, *, query):
    """Help topics for `ctx`'s own app whose title, tags or ``explains`` mention ``query`` (case-insensitive);
    every topic for this app, by title, if ``query`` is blank. A topic that names no app at all is for every app.
    Each result is a summary (`id`, `title`, `apps`, `tags`); fetch the body with `help_topic`. Topics come in the
    language of the connection (the `locale` of `hello`) where they have been translated, else in English."""
    found = default_library().search(query, app=ctx.document.model.app, language=ctx.locale)
    return [topic.summary() for topic in found]


@core_methods.method("help_topic", "id:str")
def _help_topic(ctx, *, id):
    """One help topic in full, by the id a `help_search` result gave. Unlike `help_search`, not re-scoped to
    `ctx`'s own app: an id already names one exact topic, the same way a direct link works wherever it came from. In
    the language of the connection where it has been translated, else in English (`language` says which)."""
    topic = default_library().get(id, ctx.locale)
    if topic is None:
        raise RequestError("command_error", msg("no help topic {id!r}", id=id))
    return topic.to_data()


# -- language (E5.7, D323)
@core_methods.method("set_locale", "locale:str")
def _set_locale(ctx, *, locale):
    """The interface language of this window changed (the person chose another one): what the server says to it from
    now on, errors and help, is in it where there is a translation. Like the `locale` of `hello` it is only ever the
    client's own setting, so anybody may set it, a viewer too; answers `{locale}`, as understood."""
    chosen = normalize_locale(locale)
    ctx.set_locale(chosen)
    return {"locale": chosen}


# -- reading
@core_methods.method("ping")
def _ping(ctx):
    """The current revision of the document's line (and a cheap liveness check)."""
    return {"revision": _rev_text(ctx.document.revision), "line": ctx.document.branch}


def _rev_text(revision: Revision | None) -> str | None:
    return None if revision is None else revision.to_data()


@core_methods.method("snapshot")
def _snapshot(ctx):
    """The whole state of the document and the revision it is at (can be large; apps offer viewports)."""
    doc = ctx.document
    return {
        "revision": _rev_text(doc.revision),
        "line": doc.branch,
        "app": doc.model.app,
        "state_schema": doc.model.state_schema,
        "state": doc.model.serialize(),
    }


@core_methods.method("lines")
def _lines(ctx):
    """The lines of the document's history: the active one and the side lines a restore left behind."""
    return [
        {
            "name": line.name,
            "head": _rev_text(line.head),
            "active": line.active,
            "forked_from": _rev_text(line.forked_from),
        }
        for line in ctx.document.lines()
    ]


@core_methods.method("peek_line", "line:str")
def _peek_line(ctx, line):
    """A read-only look at any line (active or hidden), without switching to it (E3.8): its revision and full
    state, in the shape of `snapshot`. For previewing before suggesting a restore or a switch. `command_error` for
    a name that is not a line of this document."""
    model = ctx.document.peek_line(line)
    return {
        "line": line,
        "revision": _rev_text(ctx.document.log.head(line)),
        "app": model.app,
        "state_schema": model.state_schema,
        "state": model.serialize(),
    }


@core_methods.method("restore_policy")
def _restore_policy(ctx):
    """How silence at a suggestion's deadline is read (E3.7): `consensus` (must actively agree) or `veto` (must
    actively object). One choice for the whole document, an owner's to make (`set_restore_policy`)."""
    return {"policy": ctx.restore.policy}


@core_methods.method("set_restore_policy", "policy:str", write=True)
def _set_restore_policy(ctx, policy):
    """Owners only: choose `consensus` or `veto` for this document (see `restore_policy`)."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document sets this"))
    if policy not in POLICIES:
        raise RequestError(
            "bad_request", msg("set_restore_policy: policy must be one of {policies}", policies=POLICIES)
        )
    ctx.restore.policy = policy
    return {"policy": policy}


@core_methods.method("propose_restore", "checkpoint:int", write=True)
def _propose_restore(ctx, checkpoint):
    """Suggest going back to a checkpoint (E3.7). Everybody connected now as an owner or editor must agree before
    it happens — unless you are the only one, in which case it happens at once, same as `branch` always does.
    `command_error` for an unknown checkpoint number, or if a suggestion is already open (`restore_proposed`'s
    `proposal`, or `null`, says); withdraw or answer that one first."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not suggest restoring a checkpoint"))
    info = next((c for c in ctx.document.checkpoints if c.number == checkpoint), None)
    if info is None:
        raise RequestError("command_error", msg("no checkpoint number {checkpoint}", checkpoint=checkpoint))
    try:
        proposal, applied = ctx.restore.propose(
            kind="restore",
            by=ctx.user,
            checkpoint=checkpoint,
            line=None,
            label=f"checkpoint “{info.label}”",
            group=ctx.editors(),
        )
    except RestoreError as exc:
        raise RequestError("command_error", str(exc)) from exc
    if proposal is not None:
        ctx.broadcast({"event": "restore_proposed", "data": proposal.to_data()})
    return {"applied": applied, "proposal": None if proposal is None else proposal.to_data()}


@core_methods.method("propose_switch", "line:str", write=True)
def _propose_switch(ctx, line):
    """Suggest making another line active again, such as the way back after a restore (E3.7). Same consent as
    `propose_restore`. `command_error` for a name that is not a line of this document, or if a suggestion is
    already open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not suggest switching lines"))
    if line not in {x.name for x in ctx.document.lines()}:
        raise RequestError("command_error", msg("there is no line called {line!r}", line=line))
    try:
        proposal, applied = ctx.restore.propose(
            kind="switch", by=ctx.user, checkpoint=None, line=line, label=f"line “{line}”", group=ctx.editors()
        )
    except RestoreError as exc:
        raise RequestError("command_error", str(exc)) from exc
    if proposal is not None:
        ctx.broadcast({"event": "restore_proposed", "data": proposal.to_data()})
    return {"applied": applied, "proposal": None if proposal is None else proposal.to_data()}


@core_methods.method("answer_restore", "agree:bool", write=True)
def _answer_restore(ctx, agree):
    """Agree or decline the open suggestion (E3.7). Resolves it at once if that was the last answer needed, or the
    moment anybody declines. `command_error` if nothing is open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not vote"))
    try:
        outcome = ctx.restore.answer(user=ctx.user, agree=agree)
    except RestoreError as exc:
        raise RequestError("command_error", str(exc)) from exc
    if outcome is None:
        ctx.broadcast({"event": "restore_proposed", "data": ctx.restore.open_proposal.to_data()})
    else:
        ctx.broadcast({"event": "restore_resolved", "data": {"outcome": outcome}})
    return {"resolved": outcome}


@core_methods.method("discard_side_history", write=True)
def _discard_side_history(ctx):
    """Owners only: permanently forget every hidden line (E3.8) — everything a restore ever left behind that is
    not part of the visible history. Returns the revisions removed. `command_error` while a suggestion is open
    (answer or withdraw it first: it may be aimed at exactly what this would remove)."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document discards its hidden lines"))
    if ctx.restore.open_proposal is not None:
        raise RequestError("command_error", msg("there is an open suggestion; answer or withdraw it first"))
    return {"discarded": [rev.to_data() for rev in ctx.document.discard_side_history()]}


@core_methods.method("withdraw_restore", write=True)
def _withdraw_restore(ctx):
    """Take back the open suggestion: whoever made it, or an owner. `command_error` if nothing is open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not withdraw suggestions"))
    try:
        ctx.restore.withdraw(user=ctx.user, is_owner=ctx.account.role == "owner")
    except RestoreError as exc:
        raise RequestError("command_error", str(exc)) from exc
    ctx.broadcast({"event": "restore_resolved", "data": {"outcome": "withdrawn"}})
    return {}


@core_methods.method("changes_since", "revision:revision?")
def _changes_since(ctx, revision):
    """The entries after a revision (everything if null), for bringing a replica up to date. A revision that is not
    on the document's line any more (it went back to a checkpoint) gives the error `stale`: reload with `snapshot`."""
    try:
        return [entry.to_data() for entry in ctx.document.entries_since(revision)]
    except KeyError:
        raise RequestError(
            "stale", msg("{revision} is not part of the document's current line; reload it", revision=revision)
        ) from None


@core_methods.method("log", "limit:int=200")
def _log(ctx, limit):
    """The visible history, oldest first, as sentences for a history panel: the newest `limit` entries (1 to 5000) of
    the active line as `{revision, author, origin, time, label, summary, of}`. `summary` may name values (a cell and
    what was typed into it) and is gone from a redacted entry."""
    if not 1 <= limit <= MAX_LOG:
        raise RequestError("bad_request", msg("log: limit must be from 1 to {limit}", limit=MAX_LOG))
    entries = ctx.document.log.path(ctx.document.revision)[-limit:]
    return [
        {
            "revision": entry.rev.to_data(),
            "author": entry.author,
            "origin": entry.origin,
            "time": entry.time,
            "label": entry.command.label,
            "summary": entry.command.summary,
            "of": None if entry.of is None else entry.of.to_data(),
        }
        for entry in entries
    ]


@core_methods.method("chat_log", "limit:int=200")
def _chat_log(ctx, limit):
    """The chat this account may read, oldest first: messages for everybody and the private ones it sent or got.
    The newest `limit` (1 to 5000), each as in the `chat` event."""
    if not 1 <= limit <= MAX_LOG:
        raise RequestError("bad_request", msg("chat_log: limit must be from 1 to {limit}", limit=MAX_LOG))
    me = ctx.user.casefold()
    readable = [
        record.to_data()
        for record in ctx.document.chat
        if not record.to or me in (record.author.casefold(), record.to.casefold())
    ]
    return readable[-limit:]


@core_methods.method("history")
def _history(ctx):
    """This account's undo and redo state."""
    h = ctx.document.history_for(ctx.user)
    return {"can_undo": h.can_undo, "can_redo": h.can_redo, "undo_label": h.undo_label, "redo_label": h.redo_label}


@core_methods.method("checkpoints")
def _checkpoints(ctx):
    """The saved checkpoints of the document's line, oldest first."""
    return [_checkpoint(info) for info in ctx.document.checkpoints]


@core_methods.method("users")
def _users(ctx):
    """The names of the people connected to the document now (for addressing chat messages)."""
    return ctx.users()


# -- writing
@core_methods.method("apply", "command:dict base:revision?", write=True)
def _apply(ctx, command, base):
    """Execute a command in its stored form `{k, s, d}` as this account. `base` is the revision the client's view was
    at: if the document moved to another line meanwhile the edit is refused with `stale`. Refused with `locked` if a
    colleague holds the part it touches; `command_error` if the command itself is rejected. Nothing changes on any
    error. Refused with `forbidden` for the assistant (SEC-10): a raw command would walk around the checks an app's
    own methods make against it (`composes._people_only` and the like), whatever `apply` itself is allowed to call."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant cannot apply a raw command; use the app's own methods"))
    try:
        parsed = ctx.document.model.registry.decode(command)
    except (UnknownCommand, SchemaTooNew) as exc:
        raise RequestError("bad_request", str(exc)) from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RequestError("bad_request", msg("invalid command: {reason!r}", reason=exc)) from exc
    applied = ctx.document.execute(parsed, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


def _stepped(applied) -> dict:
    return {"applied": applied is not None, "revision": None if applied is None else applied.revision.to_data()}


@core_methods.method("undo", write=True)
def _undo(ctx):
    """Undo this account's last step. `conflict` if a colleague changed the same thing since, `locked` if somebody
    holds it."""
    return _stepped(ctx.document.undo(ctx.user))


@core_methods.method("redo", write=True)
def _redo(ctx):
    """Redo this account's last undone step. Same errors as undo."""
    return _stepped(ctx.document.redo(ctx.user))


@core_methods.method("save_checkpoint", "label:str?", write=True)
def _save_checkpoint(ctx, label):
    """File > Save: label the current state. `saved` is false if nothing changed since the last checkpoint."""
    info = ctx.document.save_checkpoint(ctx.user, label)
    return {"saved": info is not None, "checkpoint": None if info is None else _checkpoint(info)}


# -- presence and locks
@core_methods.method("presence", "regions:regions")
def _presence(ctx, regions):
    """Tell the others where you are (the regions you look at). Not a change of the document, so viewers may use it.
    Others receive an `ephemeral` event of kind `presence`."""
    ctx.document.show_presence(ctx.user, _regions_of(ctx, regions))
    return {}


@core_methods.method("lock", "regions:regions", write=True)
def _lock(ctx, regions):
    """Hold these regions while you edit them: others cannot change them until you unlock, move on, or go quiet.
    `locked` if a colleague holds any part. Renew by locking again."""
    ctx.document.lock(ctx.user, _regions_of(ctx, regions), ctx.lock_seconds)
    return {}


@core_methods.method("unlock", write=True)
def _unlock(ctx):
    """Let go of what you hold; you stay visible where you were."""
    hold = ctx.document.presence.of(ctx.user)
    if hold is not None:
        ctx.document.show_presence(ctx.user, hold.regions)
    return {}


# -- people
@core_methods.method("add_user", 'name:str password:str role:str="editor"')
def _add_user(ctx, name, password, role):
    """Owners only: let a person into this document with a name and a password you give them (they can keep using
    it; there is no way yet to change it). `role` is `editor` or `viewer`. Returns `{user, role}`; `command_error`
    with a sentence for the person if the name is taken or reserved or the password is too short."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document adds people to it"))
    if ctx.directory is None:
        raise RequestError("unavailable", msg("this server does not manage people"))
    if role not in ("editor", "viewer"):
        raise RequestError("bad_request", msg("add_user: role must be editor or viewer"))
    account = ctx.directory.add_user(ctx.doc_id, name, password, role)
    return {"user": account.user, "role": account.role}


@core_methods.method("new_recovery_key")
def _new_recovery_key(ctx):
    """Owners only: make a new recovery key for this document. It is the way back in for somebody who has lost their
    password (`hello` with `recovery_key`), and it is shown here, this once: the server keeps nothing of it. A key the
    document had before stops working. Returns `{recovery_key}` as 13 groups of 4 letters and digits; `unavailable`
    on a server whose documents have none."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document makes a recovery key"))
    if not isinstance(ctx.directory, RecoverableDirectory):
        raise RequestError("unavailable", msg("this server does not keep recovery keys"))
    return {"recovery_key": ctx.directory.new_recovery_key(ctx.doc_id)}


@core_methods.method("roster")
def _roster(ctx):
    """Everybody who may log in to this document, not just who is connected now, in the order they were added:
    `[{user, role}, ...]`. Needed to choose who to hand ownership to. `unavailable` on a server that does not list
    a document's people this way."""
    if not isinstance(ctx.directory, RosterDirectory):
        raise RequestError("unavailable", msg("this server does not list a document's people this way"))
    return [{"user": account.user, "role": account.role} for account in ctx.directory.list_people(ctx.doc_id)]


@core_methods.method("leave", "password:str")
def _leave(ctx, password):
    """Remove yourself from this document, confirming it is really you with your own current password. Refused if
    you are the document's only owner: make somebody else the owner first (`propose_owner`). Returns `{left:
    true}`; `unauthorized` if the password is wrong."""
    if not isinstance(ctx.directory, LeavableDirectory):
        raise RequestError("unavailable", msg("this server does not support leaving a document"))
    if not ctx.directory.leave(ctx.doc_id, ctx.user, password):
        raise RequestError("unauthorized", msg("that is not your current password"))
    ctx.document.publish("person_left", ctx.user, {"user": ctx.user})
    return {"left": True}


@core_methods.method("propose_owner", "name:str password:str")
def _propose_owner(ctx, name, password):
    """Owners only: ask `name` (who must already be an editor of this document) to become its owner instead of you,
    confirming it is really you with your own current password. They have a while to accept (`accept_owner`);
    asking again replaces a proposal they have not accepted yet. Returns `{proposed: name}`; `unauthorized` if the
    password is wrong; `command_error` with a sentence if `name` is not currently an editor."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document can hand it over"))
    if not isinstance(ctx.directory, TransferableDirectory):
        raise RequestError("unavailable", msg("this server does not support handing over ownership"))
    if not ctx.directory.propose_owner_transfer(ctx.doc_id, ctx.user, password, name):
        raise RequestError("unauthorized", msg("that is not your current password"))
    return {"proposed": name}


@core_methods.method("accept_owner", "password:str")
def _accept_owner(ctx, password):
    """Accept an ownership transfer proposed to you (`propose_owner`), confirming it is really you with your own
    current password. You are the owner from now on; reconnect to be recognised as one by the server for the rest
    of this session. Returns `{accepted: true}`; `unauthorized` if nothing is waiting for you with that password
    (none was proposed to you, it already went through, or it expired)."""
    if not isinstance(ctx.directory, TransferableDirectory):
        raise RequestError("unavailable", msg("this server does not support handing over ownership"))
    account = ctx.directory.accept_owner_transfer(ctx.doc_id, ctx.user, password)
    if account is None:
        raise RequestError("unauthorized", msg("no ownership transfer is waiting for you with that password"))
    ctx.document.publish("owner_changed", ctx.user, {"owner": account.user})
    return {"accepted": True}


@core_methods.method("delete_document", "password:str")
def _delete_document(ctx, password):
    """Owners only: remove this document from the server for good — its file, its history and its chat, everybody's
    access to it — confirming it is really you with your own current password. There is no way back from this: make
    sure everybody who needs something from the document has it first. Returns `{deleted: true}`; `unauthorized` if
    the password is wrong."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only an owner of a document may delete it"))
    if not isinstance(ctx.directory, DeletableDirectory):
        raise RequestError("unavailable", msg("this server does not support deleting a document"))
    if not ctx.directory.delete_document(ctx.doc_id, ctx.user, password):
        raise RequestError("unauthorized", msg("that is not your current password"))
    ctx.document.publish("document_deleted", ctx.user, {})
    return {"deleted": True}


@core_methods.method("export_content")
def _export_content(ctx):
    """The document's current content, as Claudia's own format — not Word, Excel or PowerPoint; import and export
    for those is separate, planned work: `{format, app, exported_at, state_schema, state}`. Does not include the
    command history or the chat (E2.9: exporting those, and importing, is not built yet)."""
    model = ctx.document.model
    exported_at = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "format": "claudia-export 1",
        "app": model.app,
        "exported_at": exported_at,
        "state_schema": model.state_schema,
        "state": model.serialize(),
    }


# -- chat
@core_methods.method("chat", "text:text ai_mode:str?", write=True)
def _chat(ctx, text, ai_mode):
    """`@username message` for one person who is connected (names may contain spaces; case does not matter), a message
    without a leading @ (or `@all message`) for everybody. Chat is kept apart from the document's changes. Returns the
    record. `ai_mode` (`act` or `suggest`) is how the sender wants the AI to treat this request if it is for the AI: it
    is not stored, and a client that sends none gets `act`."""
    try:
        mode = parse_mode(ai_mode)
    except ValueError as exc:
        raise RequestError("bad_request", msg("chat: {reason}", reason=exc)) from None
    ctx.note_ai_mode(ctx.user, mode)  # before the message: the AI hears it as it is posted
    try:
        return ctx.document.post_chat(ctx.user, text, users=ctx.users()).to_data()
    finally:
        ctx.note_ai_mode(ctx.user, None)  # whether or not the AI took it
