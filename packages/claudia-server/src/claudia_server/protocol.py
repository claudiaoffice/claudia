"""The wire protocol: which requests exist, what they accept, and what they do (E3.1).

Messages are JSON text frames.

    client -> server   {"id": 7, "method": "set_cells", "params": {"sheet": "s1", "cells": [...], "base": "main:12"}}
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
types. A person's change comes in only through an app's named methods, which build the command and check it; no method
takes a command in its stored form (D2010). A command travels in its stored form (``{"k": kind, "s": schema, "d":
data}``) only from the server to clients, in events and ``changes_since``, so the protocol never needs to know what a
spreadsheet, a text or a slide is.

Restoring a checkpoint or switching the line moves everybody, so neither happens from a bare request: an owner or
editor *suggests* it (``propose_restore``, ``propose_switch``), and it is carried out once everybody who is
connected now as an owner or editor has agreed (``answer_restore``; ``restore.py`` is the consent itself, E3.7) —
unless the one suggesting it is the only one, in which case it happens at once. Either way the result reaches
connected clients the same way: ``branch`` and ``rebuilt`` events, and the ``stale`` error for an edit that was
written against the line left behind.

This module has no web framework in it, so it is tested without sockets.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from claudia_core import (
    Document,
    Import,
    KernelError,
    RegionHeld,
    Revision,
    StaleEdit,
    UndoConflict,
)
from claudia_document_file import AuditRecord, Part, clean_details, write_export

from .ai_consent import AiConsent, ConsentBook, ConsentNotKept, consent_view
from .ai_mode import parse_mode
from .audience import Reader, may_read
from .auth import (
    WRITE_ROLES,
    Account,
    AuditDirectory,
    DeletableDirectory,
    DetailsDirectory,
    LeavableDirectory,
    PasswordDirectory,
    PeopleDirectory,
    RecoverableDirectory,
    RosterDirectory,
    SealedCopyDirectory,
    TransferableDirectory,
    UserDirectory,
)
from .help import default_library
from .i18n import localized, message_of, msg
from .planned import keep_plan
from .restore import POLICIES, RestoreCoordinator, RestoreError
from .server_settings import CLAUDE
from .throttle import Throttle

if TYPE_CHECKING:
    from claudia_core import Region

    from .containers import RenderDesk

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
    "too_many_tries": "a login came too soon after failed ones; the error carries `retry_after`, the whole seconds to "
    "wait. Nothing is locked: the same login is looked at when the wait is over",
    "too_many": "more of this than the server allows in a minute; nothing was done. Try again a little later",
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
    "document_deleted|..., sender, data}. person_left: {user}; owner_changed: {owner}; role_changed: {user, role}; "
    "person_removed: {user}; document_deleted: {}, and "
    "nothing else will ever be stored or delivered for this document — close and forget it",
    "branch": "the document moved to another line (a checkpoint was restored, or the way back was taken): {old, new, "
    "fork_point}. Everything you hold is stale: call snapshot",
    "rebuilt": "the state was rebuilt from the log (after a restore, a switch or a redaction): call snapshot",
    "redacted": "the content of these revisions and chat messages was removed: {revisions, chat}; reload chat_log",
    "thing_renamed": "an object, slide or sheet got another name: {id, name} (D550)",
    "stale": "functions the document uses changed: {functions}; results computed by them are out of date",
    "joined": "somebody connected: {id, user, color}",
    "left": "somebody disconnected: {id, user}; their presence and locks are gone if it was their last connection",
    "restore_proposed": "a suggestion to restore a checkpoint or a step, or to switch the line is open, or its answers "
    "changed (see `propose_restore`): the proposal, as `answer_restore` returns it",
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
    renderings: RenderDesk | None = None  # what makes containers (D395); ``None``: this server makes none
    original: Callable[[], bytes | None] = field(default=lambda: None)  # the imported file, if it is kept (D439)
    # What the last try to draw each container said, by container: a window that joins later hears it too.
    render_outcomes: Callable[[], dict[str, dict]] = field(default=lambda: {})
    # The fonts this server has, as a ``claudia_fonts.Catalogue`` (anything that ``resolve``s a family), or ``None``.
    font_catalogue: Callable[[], Any] = field(default=lambda: None)
    # What the owners allowed a remote AI provider in this document (E7.11); ``None``: a context that keeps none.
    consent: ConsentBook | None = None
    # Who answers `@ai` in this document now, as `Via.to_data` says it; ``None`` when nobody does.
    answering: Callable[[], dict | None] = field(default=lambda: None)
    # Whether this server has a remote AI provider the owners could allow (E7.11).
    offers_claude: Callable[[], bool] = field(default=lambda: False)

    @property
    def user(self) -> str:
        """The author of what this request changes."""
        return self.account.user

    @property
    def reader(self) -> Reader:
        """Who asks, as what she may read of the document (D2008)."""
        return Reader(self.account.user, self.account.role)

    def record_leaving(self, kind: str, fmt: str, parts: tuple[str, ...], pages: int | None = None) -> None:
        """Record that the person asking took ``parts`` of the document out in ``fmt`` (D1271): an export, a print or
        a PDF. The name is the account's, never anything the client said. Nothing happens on a server whose documents
        keep no audit chain; the people who may read the record are told with an ephemeral ``audit_recorded``."""
        if not isinstance(self.directory, AuditDirectory):
            return
        record = AuditRecord(kind, self.user, _now_text(), fmt, parts, pages)
        self.directory.record_audit(self.doc_id, record)
        self.document.publish("audit_recorded", self.user, audit_row(record))


@dataclass(frozen=True)
class Method:
    """One request: its name, parameters, whether it needs a role that may write, and the function."""

    name: str
    params: tuple[Param, ...]
    write: bool
    doc: str
    fn: Callable[..., Any] = field(repr=False)
    reads: str = (
        "content"  # the part of the document it reads (``claudia_server.audience``): a viewer holds content only
    )
    hashes: tuple[tuple[str, str], ...] = ()
    """The passwords it confirms, as ``(name, password)`` parameter pairs; ``"@user"`` is the person asking.
    The server hashes them in a thread before the request is handled (SEC-21)."""
    leaves: str | None = None
    """``export`` for a method whose answer is the document in a form that can be read outside Claudia: the server
    records it in the audit chain, for the person who asked, once the answer is made (D1271, E2.9)."""


class MethodTable:
    """The methods and parameter types of a protocol. An app extends a copy (``extended``)."""

    def __init__(self) -> None:
        self._methods: dict[str, Method] = {}
        self._kinds: dict[str, Callable[[Any, Limits], Any]] = {}

    # -- building ---------------------------------------------------------------------
    def method(
        self,
        name: str,
        spec: str = "",
        *,
        write: bool = False,
        reads: str = "content",
        hashes: tuple[tuple[str, str], ...] = (),
        leaves: str | None = None,
    ):
        """Decorator: register ``fn(ctx, **params)`` as method ``name``.

        ``spec`` lists the parameters as ``"name:type name:type=default"``. ``reads`` is the part of the document the
        method shows: ``"content"`` (the default), ``"history"`` or ``"chat"``; a person whose role holds no key of
        that part (a viewer) is refused it (D1261). ``hashes`` names the ``(name, password)`` parameter pairs a method
        confirms by hashing (``"@user"`` stands for the person asking), so that the server can do that slow work
        outside its event loop first (SEC-21, ``hashes_of``). ``leaves="export"`` marks a method whose answer is the
        document in a readable form: after it succeeds the server records the export (D1271)."""
        if reads not in tuple(Part):
            raise ValueError(f"reads must be one of {', '.join(Part)}, not {reads!r}")

        def register(fn):
            self._methods[name] = Method(
                name, _parse_params(spec), write, (fn.__doc__ or "").strip(), fn, reads, hashes, leaves
            )
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
    def hashes_of(self, raw: str | bytes, user: str) -> list[tuple[str, str]]:
        """The ``(name, password)`` pairs a request frame asks the server to hash, for the person ``user`` (SEC-21).

        Cheap for the many requests that carry no password. A frame that is malformed or names no such method gives
        ``[]``: ``dispatch`` will say what is wrong with it."""
        if b"password" not in (raw if isinstance(raw, bytes) else raw.encode("utf-8", "ignore")):
            return []
        try:
            frame = json.loads(raw)
            entry = self._methods.get(frame["method"])
            params = frame.get("params") or {}
            pairs = []
            for name_field, password_field in entry.hashes if entry else ():
                name = user if name_field == "@user" else params.get(name_field)
                password = params.get(password_field)
                if isinstance(name, str) and isinstance(password, str):
                    pairs.append((name, password))
            return pairs
        except (ValueError, KeyError, TypeError, AttributeError):
            return []

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
                    msg("{method}: {parameter} {reason}", method=entry.name, parameter=p.name, reason=message_of(exc)),
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
        if not may_read(ctx.account.role, Part(entry.reads)):
            if entry.reads == Part.CHAT:
                raise RequestError(
                    "forbidden", msg("{name} reads the chat, which is for the document's owners and editors", name=name)
                )
            raise RequestError(
                "forbidden", msg("{name} reads the history, which is for the document's owners and editors", name=name)
            )
        allowed = ctx.account.allowed_methods
        if entry.write and allowed is not None and name not in allowed:
            # SEC-10: the one place every path goes through (the wire, the assistant, a future remote engine).
            raise RequestError("forbidden", msg("{name} is not one of the methods this account may call", name=name))
        args = self.bind(entry, params, ctx.limits)
        try:
            result = entry.fn(ctx, **args)
            if entry.leaves is not None:
                parts = tuple(result.get("parts", ("content",)))
                ctx.record_leaving(entry.leaves, str(result.get("format", entry.name)), parts)
            return result
        except RequestError:
            raise
        except StaleEdit as exc:
            raise RequestError("stale", message_of(exc), detail=exc.code) from exc
        except RegionHeld as exc:  # (and UndoRefused, which is one)
            raise RequestError("locked", message_of(exc), detail=exc.code) from exc
        except UndoConflict as exc:
            raise RequestError("conflict", message_of(exc), detail=exc.code) from exc
        except (
            KernelError,
            ValueError,
            LookupError,
        ) as exc:  # a command refuses with ValueError / IndexError / KeyError; only KernelError has a `code`
            raise RequestError("command_error", message_of(exc), detail=getattr(exc, "code", None)) from exc

    def describe(self, limits: Limits | None = None) -> dict:
        """A machine-readable description of the protocol (served at /api/protocol)."""
        return {
            "protocol": PROTOCOL_VERSION,
            "framing": "JSON text frames; requests {id, method, params}; responses {id, ok, result | error}; "
            "pushed {event, data}",
            "methods": {
                m.name: {"write": m.write, "reads": m.reads, "doc": m.doc, "params": [p.to_dict() for p in m.params]}
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
            "bad_request", msg("not a region this document understands: {reason!r}", reason=message_of(exc))
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
    return {"revision": _rev_text(ctx.document.revision), "branch": ctx.document.branch}


def _rev_text(revision: Revision | None) -> str | None:
    return None if revision is None else revision.to_data()


@core_methods.method("snapshot")
def _snapshot(ctx):
    """The whole state of the document and the revision it is at (can be large; apps offer viewports)."""
    doc = ctx.document
    return {
        "revision": _rev_text(doc.revision),
        "branch": doc.branch,
        "app": doc.model.app,
        "state_schema": doc.model.state_schema,
        "state": doc.model.serialize(),
    }


@core_methods.method("branches", reads="history")
def _branches(ctx):
    """The branches of the document's history: the active one and the ones a restore left behind."""
    return [
        {
            "name": branch.name,
            "head": _rev_text(branch.head),
            "active": branch.active,
            "forked_from": _rev_text(branch.forked_from),
        }
        for branch in ctx.document.branches()
    ]


@core_methods.method("peek_branch", "branch:str", reads="history")
def _peek_branch(ctx, branch):
    """A read-only look at any branch (active or hidden), without switching to it (E3.8): its revision and full
    state, in the shape of `snapshot`. For previewing before suggesting a restore or a switch. `command_error` for
    a name that is not a branch of this document."""
    model = ctx.document.peek_branch(branch)
    return {
        "branch": branch,
        "revision": _rev_text(ctx.document.log.head(branch)),
        "app": model.app,
        "state_schema": model.state_schema,
        "state": model.serialize(),
    }


@core_methods.method("restore_policy", reads="history")
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
            branch=None,
            label=f"checkpoint “{info.label}”",
            group=ctx.editors(),
        )
    except RestoreError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
    if proposal is not None:
        ctx.broadcast({"event": "restore_proposed", "data": proposal.to_data()})
    return {"applied": applied, "proposal": None if proposal is None else proposal.to_data()}


@core_methods.method("propose_restore_step", "revision:revision", write=True)
def _propose_restore_step(ctx, revision):
    """Suggest going back to the state after one step of the history (D553), the way `propose_restore` goes back to
    a checkpoint, with the same agreement: everybody connected now as an owner or editor, or at once if you are the
    only one. What came after stays on a side line. `command_error` for a step that is not on the line the document
    is on, or if a suggestion is already open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not suggest restoring a step"))
    if revision not in ctx.document.history_revisions():
        raise RequestError("command_error", msg("there is no step {revision} on this line", revision=str(revision)))
    label = ctx.document.log.get(revision).command.label
    try:
        proposal, applied = ctx.restore.propose(
            kind="restore",
            by=ctx.user,
            checkpoint=None,
            revision=revision.to_data(),
            branch=None,
            label=f"step {revision.seq} “{label}”",
            group=ctx.editors(),
        )
    except RestoreError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
    if proposal is not None:
        ctx.broadcast({"event": "restore_proposed", "data": proposal.to_data()})
    return {"applied": applied, "proposal": None if proposal is None else proposal.to_data()}


@core_methods.method("propose_switch", "branch:str", write=True)
def _propose_switch(ctx, branch):
    """Suggest making another branch active again, such as the way back after a restore (E3.7). Same consent as
    `propose_restore`. `command_error` for a name that is not a branch of this document, or if a suggestion is
    already open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not suggest switching branches"))
    if branch not in {x.name for x in ctx.document.branches()}:
        raise RequestError("command_error", msg("there is no branch called {branch!r}", branch=branch))
    try:
        proposal, applied = ctx.restore.propose(
            kind="switch", by=ctx.user, checkpoint=None, branch=branch, label=f"branch “{branch}”", group=ctx.editors()
        )
    except RestoreError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
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
        raise RequestError("command_error", message_of(exc)) from exc
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


# ------------------------------------------------------------------------------------------ redaction (E1.8, D726)
_REDACTION_PARAMS = "revisions:list? chat:list? parts:dict?"


def _redaction_request(ctx, revisions, chat, parts) -> dict:
    """The keyword arguments of ``plan_redaction`` from wire parameters, for someone who may redact what they name
    (D727): an owner anything she can read, an editor only her own changes and chat messages. ``forbidden`` for a
    viewer and the assistant, ``bad_request`` for parameters of the wrong shape, ``command_error`` for somebody
    else's work or a message she cannot read."""
    if ctx.account.system or ctx.account.role not in WRITE_ROLES:
        raise RequestError("forbidden", msg("only owners, and editors on their own work, redact"))
    try:
        steps = [Revision.parse(text) for text in revisions or ()]
        wanted = {Revision.parse(rev): [str(thing) for thing in things] for rev, things in (parts or {}).items()}
        numbers = [int(number) for number in chat or ()]
    except (ValueError, TypeError, AttributeError):
        raise RequestError(
            "bad_request", msg('redaction: revisions like "main:12", chat numbers, parts by revision')
        ) from None
    me = ctx.user.casefold()
    readable = {r.number: r for r in ctx.reader.chat(ctx.document.chat)}
    if not set(numbers) <= set(readable):
        raise RequestError("command_error", msg("there is no chat message of that number for you"))
    if ctx.account.role != "owner":
        authors = [ctx.document.log.get(rev).author for rev in steps if ctx.document.log.has(rev)]
        authors += [readable[number].author for number in numbers]
        if any((author or "").casefold() != me for author in authors):
            raise RequestError("command_error", msg("you can redact only your own changes and messages; ask an owner"))
    return {"revisions": steps, "chat": numbers, "parts": wanted}


def _planned(ctx, revisions, chat, parts):
    try:
        return ctx.document.plan_redaction(**_redaction_request(ctx, revisions, chat, parts))
    except KernelError as exc:
        raise RequestError("command_error", message_of(exc)) from exc


def _others_reached(ctx, plan) -> list[str]:
    """Whose later steps an editor's plan would blank besides her own (D727): an owner reaches nobody's she may not."""
    if ctx.account.role == "owner":
        return []
    me = ctx.user.casefold()
    authors = {ctx.document.log.get(rev).author or "" for rev in plan.dependents}
    return sorted(author for author in authors if author.casefold() != me)


@core_methods.method("redaction_plan", _REDACTION_PARAMS + " state:bool=true", reads="history")
def _redaction_plan(ctx, revisions, chat, parts, state):
    """What redacting these steps (`revisions`, on any line) and chat messages (`chat`, by number) would do, without
    doing it (D721). Owners may name anything they can read, editors only their own work (D727). `parts` blanks only
    some things of an imported document: `{"main:1": ["b4", "s1!A1:B9", "t2"]}` (paragraph, sheet or range, slide,
    object).

    Returns `{targets, dependents, chat, imports, changes_now, allowed, others, steps, app, plan, regions,
    state_schema, state}`: `dependents` are later steps that stop working without the content and are blanked with it
    (D722), `imports` the targets whose kept original goes too, `steps` every step that is blanked as `log` gives it,
    `state` the document as it will look (left out when `state` is false or the plan is not allowed). `plan` is a token
    for that state: the views read it through `as_planned` to draw the preview, and `regions` are the places in it to
    mark. `allowed` is false when an editor's plan would blank later steps by somebody else, named in `others`: an
    owner has to do it. Nothing changes. `command_error` for something the document does not have, or that cannot be
    redacted."""
    plan = _planned(ctx, revisions, chat, parts)
    out = {
        "targets": [rev.to_data() for rev in plan.targets],
        "dependents": [rev.to_data() for rev in plan.dependents],
        "chat": list(plan.chat),
        "imports": [rev.to_data() for rev in plan.imports],
        "changes_now": plan.changes_now,
        "steps": [_entry_view(ctx.document.log.get(rev)) for rev in plan.revisions],
        "app": plan.after.app,
    }
    out["others"] = _others_reached(ctx, plan)
    out["allowed"] = not out["others"]
    if out["allowed"]:
        out["plan"] = keep_plan(ctx.document, plan.after)
        out["regions"] = [region.to_data() for region in plan.regions]
    if state and out["allowed"]:
        out["state_schema"] = plan.after.state_schema
        out["state"] = plan.after.serialize()
    return out


@core_methods.method("redact", _REDACTION_PARAMS + " dependents:list", write=True)
def _redact(ctx, revisions, chat, parts, dependents):
    """Carry out the redaction `redaction_plan` showed (D229), with the same rights (D727). `dependents` repeats the
    dependents the plan named, as the confirmation that they were shown: if the plan now names others (somebody worked
    in between), nothing happens and the error is `command_error`. The content goes from the document, its history and
    its file (D725); everybody gets `redacted` (and `rebuilt` when steps were blanked). Returns `{revision}` of the
    record. `command_error` while a suggestion to restore is open. A note to the people concerned (D728) is an ordinary
    `chat` the client sends afterwards."""
    if ctx.restore.open_proposal is not None:
        raise RequestError("command_error", msg("there is an open suggestion; answer or withdraw it first"))
    plan = _planned(ctx, revisions, chat, parts)
    if others := _others_reached(ctx, plan):
        raise RequestError(
            "command_error",
            msg("this would also blank later changes by {names}; ask an owner", names=", ".join(others)),
        )
    if [rev.to_data() for rev in plan.dependents] != list(dependents):
        raise RequestError(
            "command_error", msg("the redaction would now blank other steps than you were shown; look at it again")
        )
    try:
        applied = ctx.document.redact(plan, author=ctx.user)
    except KernelError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
    return {"revision": applied.revision.to_data()}


@core_methods.method("withdraw_restore", write=True)
def _withdraw_restore(ctx):
    """Take back the open suggestion: whoever made it, or an owner. `command_error` if nothing is open."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not withdraw suggestions"))
    try:
        ctx.restore.withdraw(user=ctx.user, is_owner=ctx.account.role == "owner")
    except RestoreError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
    ctx.broadcast({"event": "restore_resolved", "data": {"outcome": "withdrawn"}})
    return {}


@core_methods.method("changes_since", "revision:revision?", reads="history")
def _changes_since(ctx, revision):
    """The entries after a revision (everything if null), for bringing a replica up to date. A revision that is not
    on the document's line any more (it went back to a checkpoint) gives the error `stale`: reload with `snapshot`."""
    try:
        return [entry.to_data() for entry in ctx.document.entries_since(revision)]
    except KeyError:
        raise RequestError(
            "stale", msg("{revision} is not part of the document's current line; reload it", revision=revision)
        ) from None


@core_methods.method("log", "limit:int=200", reads="history")
def _log(ctx, limit):
    """The visible history, oldest first, as sentences for a history panel: the newest `limit` entries (1 to 5000) of
    the active line as `{revision, author, origin, time, label, summary, of}`. `summary` may name values (a cell and
    what was typed into it) and is gone from a redacted entry."""
    if not 1 <= limit <= MAX_LOG:
        raise RequestError("bad_request", msg("log: limit must be from 1 to {limit}", limit=MAX_LOG))
    return [_entry_view(entry) for entry in ctx.document.log.path(ctx.document.revision)[-limit:]]


def _entry_view(entry) -> dict:
    """One step of the history as a history panel shows it: `{revision, author, origin, time, label, summary, of, kind,
    redacted}`; `kind` is the command's (`core.Redaction` for the record of a redaction), `redacted` whether its content
    was taken away (D720). The import of an owner's export also has `original`, the history of the document it was made
    of as `[{when, who, what, said}]`, oldest first (D2005)."""
    view = {
        "revision": entry.rev.to_data(),
        "author": entry.author,
        "origin": entry.origin,
        "time": entry.time,
        "label": entry.command.label,
        "summary": entry.command.summary,
        "of": None if entry.of is None else entry.of.to_data(),
        "kind": entry.command.kind,
        "redacted": entry.redacted,
    }
    if isinstance(entry.command, Import) and entry.command.original:
        view["original"] = [line.to_data() for line in entry.command.original]
    return view


@core_methods.method("peek_revision", "revision:revision state:bool=true", reads="history")
def _peek_revision(ctx, revision, state):
    """A read-only look at the document after one step of its history, on any line, for replaying it (D551): `{revision,
    entry, focus, app, state_schema, state}`. `entry` is the step as `log` gives it; `focus` lists the regions the step
    touched (`{kind: "objects", holder, ids}` for things on a slide or sheet, `{kind: "cells", ...}` for cells), the
    places a view brings into sight; `state` is the full state in the shape of `snapshot` and is left out when `state`
    is false, for a client that only wants to know where. Nothing changes; anybody who may read may look.
    `command_error` for a revision the document does not have."""
    try:
        look = ctx.document.peek_revision(revision)
    except KernelError as exc:
        raise RequestError("command_error", message_of(exc)) from exc
    out = {
        "revision": revision.to_data(),
        "entry": _entry_view(look.entry),
        "focus": [region.to_data() for region in look.focus],
        "app": look.model.app,
    }
    if state:
        out["state_schema"] = look.model.state_schema
        out["state"] = look.model.serialize()
    return out


@core_methods.method("chat_log", "limit:int=200", reads="chat")
def _chat_log(ctx, limit):
    """The chat this account may read, oldest first: messages for everybody and the private ones it sent or got.
    The newest `limit` (1 to 5000), each as in the `chat` event."""
    if not 1 <= limit <= MAX_LOG:
        raise RequestError("bad_request", msg("chat_log: limit must be from 1 to {limit}", limit=MAX_LOG))
    return [record.to_data() for record in ctx.reader.chat(ctx.document.chat)[-limit:]]


@core_methods.method("history", reads="history")
def _history(ctx):
    """This account's undo and redo state."""
    h = ctx.document.history_for(ctx.user)
    return {"can_undo": h.can_undo, "can_redo": h.can_redo, "undo_label": h.undo_label, "redo_label": h.redo_label}


@core_methods.method("checkpoints", reads="history")
def _checkpoints(ctx):
    """The saved checkpoints of the document's line, oldest first."""
    return [_checkpoint(info) for info in ctx.document.checkpoints]


@core_methods.method("users")
def _users(ctx):
    """The names of the people connected to the document now (for addressing chat messages)."""
    return ctx.users()


# -- writing


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
@core_methods.method("add_user", 'name:str password:str role:str="editor"', hashes=(("name", "password"),))
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


@core_methods.method("change_role", "name:str role:str")
def _change_role(ctx, name, role):
    """Owners only: give `name` the role `editor` or `viewer` (D1263). Lowering an editor to viewer renews the history
    and chat keys of the document, which takes about as long as writing its file once; raising one renews nothing.
    The person's open windows have the new role at once. An owner's role is not changed here (ownership is handed
    over, `propose_owner`). Returns `{user, role, renewed}` (`renewed` says whether keys were renewed);
    `command_error` with a sentence for the person if `name` is an owner."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document changes who may do what"))
    if not isinstance(ctx.directory, PeopleDirectory):
        raise RequestError("unavailable", msg("this server does not change roles"))
    if role not in ("editor", "viewer"):
        raise RequestError("bad_request", msg("change_role: role must be editor or viewer"))
    return _people_change(ctx, name, lambda: ctx.directory.set_role(ctx.doc_id, name, role), "role_changed")


@core_methods.method("remove_person", "name:str")
def _remove_person(ctx, name):
    """Owners only: take `name` out of this document and renew the keys she held (D1263). She keeps what she has already
    seen and any copy of the file she holds; the new keys protect what is written from now on. Her private notes are
    deleted. People who are here stay connected; her windows are told and answer nothing more. An owner cannot be
    removed here (she `leave`s, after ownership was handed over). Returns `{user}`; `command_error` with a sentence
    for the person if `name` is an owner."""
    if ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only the owner of a document removes people from it"))
    if not isinstance(ctx.directory, PeopleDirectory):
        raise RequestError("unavailable", msg("this server does not remove people"))
    return _people_change(ctx, name, lambda: ctx.directory.remove_person(ctx.doc_id, name), "person_removed")


def _people_change(ctx, name, act, kind):
    """Run a change of the people and tell the document's windows; the answer is what the caller returns."""
    before = {a.user: a.role for a in ctx.directory.list_people(ctx.doc_id)} if kind == "role_changed" else {}
    try:
        account = act()
    except KeyError:
        raise RequestError("command_error", msg("there is nobody called {name} in this document", name=name)) from None
    except ValueError as error:
        raise RequestError("command_error", message_of(error)) from error
    data = {"user": account.user}
    if kind == "role_changed":
        data["role"] = account.role
    ctx.document.publish(kind, ctx.user, data)
    if kind == "person_removed":
        return {"user": account.user}
    lowered = before.get(account.user) in ("owner", "editor") and account.role == "viewer"
    return {"user": account.user, "role": account.role, "renewed": lowered}


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


@core_methods.method("leave", "password:str", hashes=(("@user", "password"),))
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


@core_methods.method(
    "change_password",
    "old_password:str new_password:str",
    hashes=(("@user", "old_password"), ("@user", "new_password")),
)
def _change_password(ctx, old_password, new_password):
    """Choose a new password for this document, confirming it is really you with your current one (D448). Only your
    own, whatever your role; everybody else keeps theirs. Returns `{changed: true}`; `unauthorized` if the current
    password is wrong; `command_error` with a sentence for the person if the new one is not acceptable."""
    if not isinstance(ctx.directory, PasswordDirectory):
        raise RequestError("unavailable", msg("this server does not support changing a password"))
    try:
        changed = ctx.directory.change_password(ctx.doc_id, ctx.user, old_password, new_password)
    except ValueError as error:
        raise RequestError("command_error", message_of(error)) from error
    if not changed:
        raise RequestError("unauthorized", msg("that is not your current password"))
    return {"changed": True}


@core_methods.method("propose_owner", "name:str password:str", hashes=(("@user", "password"),))
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


@core_methods.method("accept_owner", "password:str", hashes=(("@user", "password"),))
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


@core_methods.method("delete_document", "password:str", hashes=(("@user", "password"),))
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


@core_methods.method("set_details", "password:str description:text tags:list", hashes=(("@user", "password"),))
def _set_details(ctx, password, description, tags):
    """Owners and editors: say what this document is about. `description` is Markdown, `tags` a list of short words;
    both replace what was there, and both are kept in the plain part of the document file so that everybody who may
    list the server can read and search them, without a password. They are not part of the history. You confirm it is
    really you with your own password; a viewer may not. Returns `{description, tags}` as kept;
    `unauthorized` if the password is wrong; `command_error` with a sentence if a text is too long or there are too
    many tags."""
    if ctx.account.role not in ("owner", "editor"):
        raise RequestError(
            "forbidden", msg("only an editor or an owner of a document may change its description and tags")
        )
    if not isinstance(ctx.directory, DetailsDirectory):
        raise RequestError("unavailable", msg("this server does not keep a description and tags"))
    if not all(isinstance(tag, str) for tag in tags):
        raise RequestError("bad_request", msg("tags are words"))
    try:
        changed = ctx.directory.set_details(ctx.doc_id, ctx.user, password, description, tags)
    except ValueError as error:
        raise RequestError("command_error", message_of(error)) from error
    if not changed:
        raise RequestError("unauthorized", msg("that is not your current password"))
    kept_description, kept_tags = clean_details(description, tags)
    ctx.document.publish("details_changed", ctx.user, {"description": kept_description, "tags": list(kept_tags)})
    return {"description": kept_description, "tags": list(kept_tags)}


def _now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def audit_row(record: AuditRecord) -> dict:
    """A record as the wire shows it: `{kind, who, when, format, parts, pages}`."""
    return {
        "kind": record.kind,
        "who": record.who,
        "when": record.when,
        "format": record.format,
        "parts": list(record.parts),
        "pages": record.pages,
    }


@core_methods.method("export_content", leaves="export")
def _export_content(ctx):
    """The document's current content, as Claudia's own format — not Word, Excel or PowerPoint; import and export
    for those is separate, planned work: `{format, app, exported_at, state_schema, state}`. Does not include the
    command history or the chat (E2.9: exporting those, and importing, is not built yet)."""
    model = ctx.document.model
    return {
        "format": "claudia-export 1",
        "app": model.app,
        "exported_at": _now_text(),
        "state_schema": model.state_schema,
        "state": model.serialize(),
    }


@core_methods.method("export_claudia", "include_history:bool=false", leaves="export")
def _export_claudia(ctx, include_history):
    """File ▸ Export… ▸ Claudia, unencrypted (D1270): one zip anybody can read, with the document's content as
    `content.json` and, if an owner asks for it with `include_history`, the history (hidden side lines included) and
    the chat as `history.jsonl` and `chat.jsonl`: the chat she may read, not the private messages between other people
    (SEC-24, D2008). No keys, no password hashes, no people. It is recorded in the
    document (D1271) as an export by you. Returns `{format: "claudia-unencrypted", filename, content_type, data
    (base64), parts}`; `forbidden` if `include_history` is asked by anybody but an owner. The AI may not export."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not export the document"))
    if include_history and ctx.account.role != "owner":
        raise RequestError("forbidden", msg("only an owner may export the history and the chat"))
    model = ctx.document.model
    history = chat = None
    if include_history:
        from .filestore import (  # noqa: PLC0415 - filestore needs the hub, which needs us
            chat_payloads,
            history_payloads,
        )

        history = history_payloads(ctx.document.log)
        chat = chat_payloads(ctx.reader.chat(ctx.document.chat))  # what she may read of it (SEC-24, D2008)
    data = write_export(
        model.app,
        model.state_schema,
        model.serialize(),
        exporter=ctx.user,
        exported_at=_now_text(),
        history=history,
        chat=chat,
    )
    return {
        "format": "claudia-unencrypted",
        "filename": f"{ctx.doc_id}.claudia-export.zip",
        "content_type": "application/zip",
        "data": base64.b64encode(data).decode("ascii"),
        "parts": ["content", "history", "chat"] if include_history else ["content"],
    }


_REPORTS: WeakKeyDictionary[Document, Throttle] = WeakKeyDictionary()
"""How often a person's client may report a print or a PDF, per document: a script cannot fill the file (D1271)."""
REPORTS_PER_MINUTE = 20
MAX_REPORTED_PAGES = 100_000


@core_methods.method("report_output", "kind:str format:str pages:int")
def _report_output(ctx, kind, format, pages):
    """A print or a PDF that this window has just made (D1271): `kind` is `print` or `pdf`, `format` what it was made
    as (`print`, `pdf`), `pages` how many pages the document has. The server records who did it: you, from your
    connection. This is the client's report of what Claudia's own screens did, not a guarantee, and it is made when the
    file is saved or the page sent to the printer, not when the preview opens. At most 20 a minute for each person;
    `too_many` after that. Any role may report, a viewer too, and the assistant may not."""
    if ctx.account.system:
        raise RequestError("forbidden", msg("the assistant does not print"))
    if kind not in ("print", "pdf"):
        raise RequestError("bad_request", msg("report_output: kind must be print or pdf"))
    if not 0 <= pages <= MAX_REPORTED_PAGES or not 0 < len(format) <= 40:
        raise RequestError("bad_request", msg("report_output: pages and format are not usable"))
    throttle = _REPORTS.setdefault(ctx.document, Throttle(REPORTS_PER_MINUTE, 60.0))
    if not throttle.allow(ctx.user.casefold()):
        raise RequestError("too_many", msg("that is more prints and PDFs than the document records in a minute"))
    ctx.record_leaving(kind, format, ("content",), pages)
    return {"recorded": True}


@core_methods.method("audit_log", reads="history")
def _audit_log(ctx):
    """What has left the document in a form that can be read outside Claudia, oldest first, as `{kind, who, when,
    format, parts, pages}` (D1271): exports in any format, prints and PDFs. For owners and editors; a viewer does not
    see it. The record cannot be redacted and has no revision."""
    if not isinstance(ctx.directory, AuditDirectory):
        return []
    return [audit_row(record) for record in ctx.directory.audit_rows(ctx.doc_id)]


@core_methods.method("ai_consent")
def _ai_consent(ctx):
    """Whether the owners allowed Claude to be sent this document's content when somebody asks `@ai` here (D264): off
    until an owner says so. Any role may read it, a viewer too. Returns `{provider, allowed, by, at, owners,
    history, answering, offered}`: `by` and `at` are who decided last and when, `owners` the people who can change it,
    `history` every decision (`{allowed, who, when}`) oldest first, `answering` who answers `@ai` here now (`{provider,
    label, remote, note}`; `note` says why it is not Claude where it is not), `offered` whether this server has
    Claude set up, so that there is something to allow."""
    state = ctx.consent.state if ctx.consent is not None else AiConsent()
    return _consent_answer(ctx, state)


@core_methods.method("set_ai_consent", "allowed:bool", write=True)
def _set_ai_consent(ctx, allowed):
    """Owners only: allow (`allowed` true) or withdraw Claude being sent this document's content when somebody asks
    `@ai` here. Recorded in the document file with who and when; it is not a change of the document and cannot be
    undone like one. Switching it off stops a question that is running before its next step. Returns what
    `ai_consent` returns. `forbidden` for anybody who is not an owner; `unavailable` on a server that keeps no
    document files, where it is always off."""
    if ctx.account.role != "owner" or ctx.account.system:
        raise RequestError("forbidden", msg("only the owner of a document decides whether Claude may be asked here"))
    if ctx.consent is None:
        raise RequestError("unavailable", msg("this server cannot keep the owner's consent, so Claude is not allowed"))
    try:
        record = ctx.consent.decide(CLAUDE, allowed, ctx.user, _now_text())
    except ConsentNotKept:
        raise RequestError(
            "unavailable", msg("this server cannot keep the owner's consent, so Claude is not allowed")
        ) from None
    view = _consent_answer(ctx, ctx.consent.state)
    if record is not None:
        ctx.document.publish("ai_consent_changed", ctx.user, {"allowed": allowed, "by": ctx.user, "at": record.when})
    return view


def _consent_answer(ctx, state: AiConsent) -> dict:
    return {
        **consent_view(state, CLAUDE, _owners(ctx)),
        "answering": ctx.answering(),
        "offered": ctx.offers_claude(),
    }


def _owners(ctx) -> list[str]:
    """The people who can change the consent: the document's owners, as the directory names them."""
    if not isinstance(ctx.directory, RosterDirectory):
        return [ctx.user] if ctx.account.role == "owner" else []
    return [account.user for account in ctx.directory.list_people(ctx.doc_id) if account.role == "owner"]


@core_methods.method("download_claudia", "password:str", hashes=(("@user", "password"),))
def _download_claudia(ctx, password):
    """File ▸ Download (D110, D1270): the document as Claudia's own sealed file, to keep on your computer. An owner
    gets the whole file; an editor gets it with only her own key slot; a viewer gets only what the content key opens
    (no history, no chat) and her own slot. It opens with your name and password, as a copy of its own and not as the
    live document. You confirm it is really you with your own current password: it is also what finds your slot.
    Returns `{format: "claudia", filename, content_type, data (base64), parts}` with `parts` naming what the file
    holds (`content`, and for an owner or an editor `history` and `chat`); `unauthorized` if the password is wrong;
    `unavailable` on a server that keeps no Claudia files."""
    if not isinstance(ctx.directory, SealedCopyDirectory):
        raise RequestError("unavailable", msg("this server does not keep documents as files you can download"))
    try:
        data = ctx.directory.sealed_copy(ctx.doc_id, ctx.user, password)
    except ValueError as error:
        raise RequestError("command_error", message_of(error)) from error
    if data is None:
        raise RequestError("unauthorized", msg("that is not your current password"))
    parts = ["content"] if ctx.account.role == "viewer" else ["content", "history", "chat"]
    return {
        "format": "claudia",
        "filename": f"{ctx.doc_id}.claudia",
        "content_type": "application/x-claudia-document",
        "data": base64.b64encode(data).decode("ascii"),
        "parts": parts,
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
        raise RequestError("bad_request", msg("chat: {reason}", reason=message_of(exc))) from None
    ctx.note_ai_mode(ctx.user, mode)  # before the message: the AI hears it as it is posted
    try:
        return ctx.document.post_chat(ctx.user, text, users=ctx.users()).to_data()
    finally:
        ctx.note_ai_mode(ctx.user, None)  # whether or not the AI took it
