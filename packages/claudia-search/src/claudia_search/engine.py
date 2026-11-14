"""Search: what a person wants to find, compiled to a pattern and run on texts (E1.12, D281-D284).

A person describes a search in one of three ways, and all three end in the same :class:`CompiledSearch`:

* **text**: what is typed is what is found; nothing in it is a pattern (the quick find field);
* **builder**: *parts* to find, in order (what x how many, optionally *kept* under a name), and *conditions* on the
  whole text (contains, does not contain, ...); the vocabulary of ``claudiaoffice-log/notes/search-and-replace.md``;
* **pattern**: the person's own text, as three fields: the pattern to find, a *filter* the whole text must match
  (both in Python's ``re`` syntax) and a replacement.

The engine knows no app and no language: it works on plain texts and returns spans. An app adds parts of its own
(computes: a cell reference) by handing their sources to :meth:`Query.compile`. How a search is phrased to a person
(the sentence that restates it) is the client's, because it needs the person's language.

Patterns are read by Python's ``re`` (its syntax is what a person is told, and its messages are what clients explain)
and run on the ``regex`` package (D287), in its version 0 syntax, which reads them the same way. Unlike ``re`` it can be
stopped: every call that runs a pattern takes a *deadline* (a :func:`time.monotonic` time) and raises
:class:`SearchTimeout` when it passes, so a pattern that backtracks without end costs its caller a bounded time and
never the server (SEC-18). Without a deadline a call may take :data:`MAX_SECONDS` at most. An earlier version refused
such patterns by their shape instead; that guess missed some and refused good ones. A dot matches line breaks too,
because a cell or a paragraph may hold them.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import regex

MAX_PATTERN_CHARS = 2000  # a typed pattern, or the one the builder made
MAX_PARTS = 30
MAX_CONDITIONS = 10
MAX_REPLACEMENT_ITEMS = 50
MAX_TEXT_CHARS = 1000  # a text to find, a part's text, a replacement's literal
MAX_SET_CHARS = 200  # the characters of "any one of"
MAX_COUNT = 1000  # "exactly n" and "n to m"
MAX_SECONDS = 1.0  # what one call may take when its caller gives no deadline

MODES = ("text", "builder", "pattern")
WHOLE = ("none", "entire", "word")
COMBINE = ("all", "any")
COUNTS = ("once", "optional", "one_or_more", "any", "exactly", "between")
CONDITIONS = (
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "is",
    "contains_any_of",
    "not_contains_any_of",
)
_WITH_TEXT = {"contains", "not_contains", "starts_with", "ends_with", "is"}
_WITH_CHARS = {"contains_any_of", "not_contains_any_of"}

_SIMPLE = {  # parts that need nothing but their name; every one except ``number`` is one character wide
    "letter": r"[^\W\d_]",
    "digit": r"\d",
    "space": r"\s",
    "any": ".",
    "number": r"\d+(?:[.,]\d+)*",
    "start": "^",
    "end": r"\Z",
}
_POSITIONS = {"start", "end"}  # a place, not a thing: it cannot be repeated
_ONE_WIDE = {"letter", "digit", "space", "any", "any_of", "none_of"}
_QUANTIFIER = {"optional": "?", "one_or_more": "+", "any": "*"}
_TEXT_PARTS = {"text", "any_of", "none_of"}

_KEYS = {
    "text": {"mode", "text", "match_case", "whole", "replace"},
    "builder": {"mode", "parts", "conditions", "combine", "match_case", "whole", "replace"},
    "pattern": {"mode", "find", "filter", "replace", "match_case"},
}


class SearchError(ValueError):
    """A search that cannot be run, with a plain-language ``message``.

    ``field`` names where the mistake is (``"find"``, ``"filter"`` or ``"replace"`` for a typed pattern; ``"query"`` for
    the search as a whole) and ``position`` is the character in that field, when the pattern parser knows it."""

    def __init__(self, message: str, field: str = "query", position: int | None = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.position = position


class SearchTimeout(Exception):
    """The deadline passed while a pattern was running. Not a mistake in the search: on another text, or with more
    time, it may finish. A caller reports how far it got."""


def _fail(message: str) -> SearchError:
    return SearchError(message)


# --- reading what a client sent -------------------------------------------------------------------------------------


def _text(value: Any, what: str, limit: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise _fail(f"{what} must be text of 1 to {limit} characters")
    return value


def _whole_number(value: Any, what: str, low: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= MAX_COUNT:
        raise _fail(f"{what} must be a whole number from {low} to {MAX_COUNT}")
    return value


def _only(data: dict, allowed: set[str], what: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise _fail(f"{what} has no {', '.join(sorted(unknown))}")


@dataclass(frozen=True)
class Part:
    """One thing to find: ``what`` (``text``, ``any_of``, ``none_of``, ``letter``, ``digit``, ``space``, ``any``,
    ``number``, ``start``, ``end``, or a part an app adds), how many of it, and optionally a name to keep it under."""

    what: str
    value: str | None = None
    chars: str | None = None
    count: str | None = None
    n: int | None = None
    m: int | None = None
    keep: str | None = None

    @classmethod
    def from_data(cls, data: Any) -> Part:
        """The part ``data`` describes (``{what, value?, chars?, count?, n?, m?, keep?}``), or :class:`SearchError`."""
        if not isinstance(data, dict) or not isinstance(data.get("what"), str) or not data["what"]:
            raise _fail("a part says what it is: {what: ...}")
        _only(data, {"what", "value", "chars", "count", "n", "m", "keep"}, "a part")
        what = data["what"]
        if what == "text" and "value" not in data:
            raise _fail("a part “text” needs its text")
        if what in ("any_of", "none_of") and "chars" not in data:
            raise _fail(f"a part “{what}” needs its characters")
        value = _text(data["value"], "the text of a part") if what == "text" else None
        chars = (
            _text(data["chars"], "the characters of a part", MAX_SET_CHARS) if what in ("any_of", "none_of") else None
        )
        count, n, m = cls._count(data, what)
        keep = data.get("keep")
        if keep is not None and (not isinstance(keep, str) or not keep or len(keep) > 60):
            raise _fail("the name a part is kept under must be text of 1 to 60 characters")
        return cls(what, value, chars, count, n, m, keep)

    @staticmethod
    def _count(data: dict, what: str) -> tuple[str | None, int | None, int | None]:
        count = data.get("count")
        if count is None:
            if "n" in data or "m" in data:
                raise _fail("n and m belong to a count of “exactly” or “between”")
            return None, None, None
        if count not in COUNTS:
            raise _fail(f"a part is counted as one of {', '.join(COUNTS)}, not {count!r}")
        if what in _POSITIONS and count != "once":
            raise _fail(f"“{what}” is a place and cannot be repeated")
        counted = count in ("exactly", "between")
        if counted and "n" not in data or count == "between" and "m" not in data:
            raise _fail(f"“{count}” needs its numbers")
        if not counted and ("n" in data or "m" in data):
            raise _fail("n and m belong to a count of “exactly” or “between”")
        n = _whole_number(data["n"], "n", 0 if count == "between" else 1) if counted else None
        m = _whole_number(data["m"], "m") if count == "between" else None
        if n is not None and m is not None and m < n:
            raise _fail("“between” needs n not larger than m")
        return count, n, m

    def to_data(self) -> dict:
        """The part as a client sends it."""
        data: dict = {"what": self.what}
        for name in ("value", "chars", "count", "n", "m", "keep"):
            if getattr(self, name) is not None:
                data[name] = getattr(self, name)
        return data


@dataclass(frozen=True)
class Condition:
    """A demand on the whole text: it contains, does not contain, starts with, ends with or is a text, or contains (or
    not) one of some characters."""

    kind: str
    text: str | None = None
    chars: str | None = None

    @classmethod
    def from_data(cls, data: Any) -> Condition:
        """The condition ``data`` describes (``{kind, text}`` or ``{kind, chars}``), or :class:`SearchError`."""
        if not isinstance(data, dict) or data.get("kind") not in CONDITIONS:
            raise _fail(f"a condition is one of {', '.join(CONDITIONS)}")
        _only(data, {"kind", "text", "chars"}, "a condition")
        kind = data["kind"]
        if kind in _WITH_TEXT:
            if "chars" in data:
                raise _fail(f"“{kind}” takes a text, not characters")
            return cls(kind, text=_text(data.get("text"), "the text of a condition"))
        if "text" in data:
            raise _fail(f"“{kind}” takes characters, not a text")
        return cls(kind, chars=_text(data.get("chars"), "the characters of a condition", MAX_SET_CHARS))

    def to_data(self) -> dict:
        """The condition as a client sends it."""
        return {"kind": self.kind, **({"text": self.text} if self.text is not None else {"chars": self.chars})}

    def body(self) -> tuple[bool, str]:
        """(``True`` if it must hold, the pattern that is looked for at the start of the text)."""
        text = re.escape(self.text) if self.text is not None else _char_class(self.chars or "")
        return {
            "contains": (True, f".*{text}"),
            "not_contains": (False, f".*{text}"),
            "starts_with": (True, text),
            "ends_with": (True, f".*{text}\\Z"),
            "is": (True, f"{text}\\Z"),
            "contains_any_of": (True, f".*{text}"),
            "not_contains_any_of": (False, f".*{text}"),
        }[self.kind]

    def source(self) -> str:
        """The condition as a look-ahead at the start of a text: what the filter of a builder search is made of."""
        must, body = self.body()
        return f"(?{'=' if must else '!'}{body})"


def _char_class(chars: str, negated: bool = False) -> str:
    unique = "".join(dict.fromkeys(chars))
    inner = "".join("\\" + c if c in "\\]^-[" else c for c in unique)
    return f"[{'^' if negated else ''}{inner}]"


def _replacement_items(value: Any) -> tuple[tuple[str, str], ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > MAX_REPLACEMENT_ITEMS:
        raise _fail(f"a replacement is a list of at most {MAX_REPLACEMENT_ITEMS} texts and kept parts")
    items = []
    for item in value:
        if not isinstance(item, dict) or len(item) != 1 or next(iter(item)) not in ("text", "keep"):
            raise _fail("each piece of a replacement is {text: ...} or {keep: ...}")
        kind, content = next(iter(item.items()))
        if not isinstance(content, str) or len(content) > MAX_TEXT_CHARS or (kind == "keep" and not content):
            raise _fail(f"a replacement's {kind} must be text of at most {MAX_TEXT_CHARS} characters")
        items.append((kind, content))
    return tuple(items)


@dataclass(frozen=True)
class Query:
    """A search as a person described it. Build it with :meth:`from_data` (it checks everything a client could get
    wrong), turn it into something that runs with :meth:`compile`."""

    mode: str
    text: str = ""
    parts: tuple[Part, ...] = ()
    conditions: tuple[Condition, ...] = ()
    combine: str = "all"
    find: str = ""
    filter: str = ""
    replace: tuple[tuple[str, str], ...] | str | None = None
    match_case: bool = False
    whole: str = "none"

    @classmethod
    def from_data(cls, data: Any) -> Query:
        """The query ``data`` describes, or :class:`SearchError` with what is wrong with it."""
        if not isinstance(data, dict) or data.get("mode") not in MODES:
            raise _fail(f"a search has a mode: one of {', '.join(MODES)}")
        mode = data["mode"]
        _only(data, _KEYS[mode], "a search in this mode")
        match_case = data.get("match_case", False)
        whole = data.get("whole", "none")
        if not isinstance(match_case, bool) or whole not in WHOLE:
            raise _fail(f"match_case is true or false, and whole is one of {', '.join(WHOLE)}")
        if mode == "pattern":
            return cls._typed(data, match_case)
        replace = _replacement_items(data.get("replace"))
        if mode == "text":
            if not isinstance(data.get("text"), str) or len(data["text"]) > MAX_TEXT_CHARS:
                raise _fail(f"the text to find must be text of at most {MAX_TEXT_CHARS} characters")
            return cls(mode, text=data["text"], replace=replace, match_case=match_case, whole=whole)
        return cls._built(data, replace, match_case, whole)

    @classmethod
    def _typed(cls, data: dict, match_case: bool) -> Query:
        for name in ("find", "filter"):
            if not isinstance(data.get(name, ""), str):
                raise _fail(f"{name} must be text")
        replace = data.get("replace")
        if replace is not None and not isinstance(replace, str):
            raise _fail("replace must be text")
        return cls(
            "pattern", find=data.get("find", ""), filter=data.get("filter", ""), replace=replace, match_case=match_case
        )

    @classmethod
    def _built(cls, data: dict, replace, match_case: bool, whole: str) -> Query:
        parts, conditions = data.get("parts", []), data.get("conditions", [])
        combine = data.get("combine", "all")
        if not isinstance(parts, list) or not isinstance(conditions, list) or combine not in COMBINE:
            raise _fail(f"parts and conditions are lists, and combine is one of {', '.join(COMBINE)}")
        if len(parts) > MAX_PARTS or len(conditions) > MAX_CONDITIONS:
            raise _fail(f"a search has at most {MAX_PARTS} parts and {MAX_CONDITIONS} conditions")
        made = tuple(Part.from_data(p) for p in parts)
        names = [p.keep for p in made if p.keep]
        for name in names:
            if names.count(name) > 1:
                raise _fail(f"two parts are kept as “{name}”: each name is used once")
        for kind, name in replace or ():
            if kind == "keep" and name not in names:
                raise _fail(f"the replacement uses “{name}”, but no part is kept under that name")
        return cls(
            "builder",
            parts=made,
            conditions=tuple(Condition.from_data(c) for c in conditions),
            combine=combine,
            replace=replace,
            match_case=match_case,
            whole=whole,
        )

    def to_data(self) -> dict:
        """The data this query was made from (defaults written out), so that it can be sent back and forth."""
        if self.mode == "pattern":
            return {
                "mode": "pattern",
                "find": self.find,
                "filter": self.filter,
                "replace": self.replace,
                "match_case": self.match_case,
            }
        items = cast("tuple[tuple[str, str], ...] | None", self.replace)
        replace = None if items is None else [{kind: content} for kind, content in items]
        shared = {"match_case": self.match_case, "whole": self.whole, "replace": replace}
        if self.mode == "text":
            return {"mode": "text", "text": self.text, **shared}
        return {
            "mode": "builder",
            "parts": [p.to_data() for p in self.parts],
            "conditions": [c.to_data() for c in self.conditions],
            "combine": self.combine,
            **shared,
        }

    # -- compiling -----------------------------------------------------------------------------------------------
    def compile(self, extra_parts: Mapping[str, str] | None = None) -> CompiledSearch:
        """The search ready to run. ``extra_parts`` maps the names of parts an app adds to their pattern source.

        Raises :class:`SearchError` for a part nobody knows, a pattern that does not read, or a replacement that names
        a group the pattern does not have."""
        find, filtered, template = self._sources(extra_parts or {})
        return CompiledSearch._make(self.match_case, find, filtered, template, self._reasons(), self.mode == "builder")

    def _sources(self, extra: Mapping[str, str]) -> tuple[str, str, str | None]:
        if self.mode == "pattern":
            return self.find, self.filter, self.replace  # type: ignore[return-value]
        if self.mode == "text":
            source = re.escape(self.text) if self.text else ""
            return self._whole(source), "", self._template()
        find = "".join(self._part_source(p, extra) for p in self.parts)
        return self._whole(find) if find else (".+" if self.conditions else ""), self._filter_source(), self._template()

    def _whole(self, source: str) -> str:
        if not source:
            return source
        return {"none": source, "entire": rf"^(?:{source})\Z", "word": rf"(?<!\w)(?:{source})(?!\w)"}[self.whole]

    @staticmethod
    def _part_source(part: Part, extra: Mapping[str, str]) -> str:
        if part.what == "text":
            base, atomic = re.escape(part.value or ""), len(part.value or "") == 1
        elif part.what in ("any_of", "none_of"):
            base, atomic = _char_class(part.chars or "", part.what == "none_of"), True
        elif part.what in _SIMPLE:
            base, atomic = _SIMPLE[part.what], part.what in _ONE_WIDE
        elif part.what in extra:
            base, atomic = extra[part.what], False
        else:
            raise _fail(f"this app knows no part called “{part.what}”")
        suffix = _suffix(part)
        if suffix and not atomic:
            base = f"(?:{base})"
        base += suffix
        return f"({base})" if part.keep else base

    def _filter_source(self) -> str:
        if not self.conditions:
            return ""
        sources = [c.source() for c in self.conditions]
        if self.combine == "any" and len(sources) > 1:
            return "^(?:" + "|".join(sources) + ")"
        return "^" + "".join(sources)

    def _template(self) -> str | None:
        if self.replace is None:
            return None
        names = [p.keep for p in self.parts if p.keep]
        pieces = []
        for kind, content in cast("tuple[tuple[str, str], ...]", self.replace):
            pieces.append(content.replace("\\", "\\\\") if kind == "text" else f"\\g<{names.index(content) + 1}>")
        return "".join(pieces)

    def _reasons(self) -> tuple[Condition, ...]:
        return self.conditions if self.mode == "builder" and self.combine == "all" else ()


def _suffix(part: Part) -> str:
    if part.count in _QUANTIFIER:
        return _QUANTIFIER[part.count]
    if part.count == "exactly":
        return f"{{{part.n}}}"
    if part.count == "between":
        return f"{{{part.n},{part.m}}}"
    return ""


# --- running ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    """One place in a text: characters ``start`` to ``end`` (end not included), what its kept parts matched, and, when
    there is a replacement, what the match would become."""

    start: int
    end: int
    kept: tuple[str, ...] = ()
    after: str | None = None


class CompiledSearch:
    """A search that can be run on any number of texts. Make one with :meth:`Query.compile`."""

    def __init__(
        self,
        find: regex.Pattern | None,
        filtered: regex.Pattern | None,
        template: str | None,
        sources: tuple[str, str, str],
        reasons: tuple[Condition, ...],
    ):
        self._find = find
        self._filter = filtered
        self._template = template
        self._sources = sources
        self._reasons = reasons

    @classmethod
    def _make(
        cls,
        match_case: bool,
        find: str,
        filter_source: str,
        template: str | None,
        reasons: tuple[Condition, ...],
        from_builder: bool,
    ) -> CompiledSearch:
        flags = regex.VERSION0 | regex.DOTALL | (0 if match_case else regex.IGNORECASE)
        found = _compile(find, "find", flags) if find else None
        filtered = _compile(filter_source, "filter", flags) if filter_source else None
        if template is not None and found is not None:
            _check_template(found, template)
        return cls(found, filtered, template, (find, filter_source, template or ""), reasons if from_builder else ())

    def pattern_text(self) -> dict[str, str]:
        """The three fields a person would type to say the same: ``find``, ``filter`` and ``replace`` (what the builder
        made, for the view that lets her edit it as text)."""
        find, filter_source, replace = self._sources
        return {"find": find, "filter": filter_source, "replace": replace}

    def admits(self, text: str, deadline: float | None = None) -> bool:
        """Whether the filter lets this text through (always, when there is none). :class:`SearchTimeout` once
        ``deadline`` (a :func:`time.monotonic` time) has passed; see the module's docstring."""
        found = self._filter
        if found is None:
            return True
        return _run(lambda timeout: found.search(text, timeout=timeout), deadline) is not None

    def matches(self, text: str, deadline: float | None = None) -> list[Match]:
        """Where in ``text`` the search finds something, in order. Nothing in a text the filter rejects, and no
        empty match. :class:`SearchTimeout` once ``deadline`` has passed."""
        return [self._match(m) for m in self._raw(text, deadline)]

    def left_out(self, text: str, deadline: float | None = None) -> dict | None:
        """Why a text that looks like a match was left out: the condition that failed (as its data),
        ``{"kind": "filter"}`` when it is the filter pattern or an "any of" that did not let it through, or ``None``
        when it was not left out (it matches, or the find finds nothing in it). :class:`SearchTimeout` once
        ``deadline`` has passed."""
        if self.admits(text, deadline) or self._find is None:
            return None
        find = self._find
        if not any(
            m.end() > m.start() for m in _run(lambda timeout: list(find.finditer(text, timeout=timeout)), deadline)
        ):
            return None
        for condition in self._reasons:
            test = regex.compile(condition.source(), self._flags())
            if _run(lambda timeout, test=test: test.match(text, timeout=timeout), deadline) is None:
                return condition.to_data()
        return {"kind": "filter"}

    def replaced(self, text: str, leave: set[int] | frozenset[int] = frozenset(), deadline: float | None = None) -> str:
        """``text`` with every match but those numbered in ``leave`` (counting from 0) replaced.

        Raises :class:`SearchError` if the search has no replacement, :class:`SearchTimeout` once ``deadline`` has
        passed."""
        if self._template is None:
            raise SearchError("there is nothing to replace with")
        out, at = [], 0
        for number, m in enumerate(self._raw(text, deadline)):
            out.append(text[at : m.start()])
            out.append(m.group() if number in leave else self._expand(m))
            at = m.end()
        out.append(text[at:])
        return "".join(out)

    # -- inside ----------------------------------------------------------------------------------------------------
    def _flags(self) -> int:
        return (self._find or self._filter).flags if (self._find or self._filter) else 0  # type: ignore[union-attr]

    def _raw(self, text: str, deadline: float | None) -> list[Any]:
        if self._find is None or not text or not self.admits(text, deadline):
            return []
        find = self._find
        found = _run(lambda timeout: list(find.finditer(text, timeout=timeout)), deadline)
        return [m for m in found if m.end() > m.start()]

    def _expand(self, m: Any) -> str:
        return m.expand(self._template or "")

    def _match(self, m: Any) -> Match:
        kept = tuple(g or "" for g in m.groups())
        return Match(m.start(), m.end(), kept, None if self._template is None else self._expand(m))


def _run(call, deadline: float | None):
    """``call(timeout)``, with what is left until ``deadline`` (or :data:`MAX_SECONDS`) as the timeout."""
    timeout = MAX_SECONDS if deadline is None else deadline - time.monotonic()
    if timeout <= 0:
        raise SearchTimeout
    try:
        return call(timeout)
    except TimeoutError:
        raise SearchTimeout from None


def _compile(source: str, field: str, flags: int) -> regex.Pattern:
    """The pattern, read by ``re`` and run by ``regex``.

    ``re`` reads it first: the syntax a person is told is Python's, and ``re`` names a mistake where it is (the
    ``(`` that is never closed, not the end of the pattern) in the words the clients explain (``explainError``). A
    pattern ``re`` reads, ``regex`` reads the same way in its version 0."""
    if len(source) > MAX_PATTERN_CHARS:
        raise SearchError(f"a pattern has at most {MAX_PATTERN_CHARS} characters", field)
    try:
        re.compile(source, re.DOTALL | (flags & regex.IGNORECASE and re.IGNORECASE))
        return regex.compile(source, flags)
    except re.error as problem:
        raise SearchError(problem.msg, field, problem.pos) from None
    except regex.error as problem:  # (a pattern `re` reads, `regex` reads too; this is the guard for when it does not)
        raise SearchError(str(problem), field, getattr(problem, "pos", None)) from None
    except RecursionError:
        raise SearchError("this pattern is nested too deeply", field) from None


def _check_template(find: regex.Pattern, template: str) -> None:
    """Whether ``template`` reads and names only groups ``find`` has. ``regex`` reads a replacement only when it is
    used; this reads it now, on an empty match of a stand-in with the same groups, so that a mistake is shown while
    the person types and not halfway through replacing."""
    names = {index: name for name, index in find.groupindex.items()}
    try:
        stand_in = re.compile("".join(f"(?P<{names[i]}>)" if i in names else "()" for i in range(1, find.groups + 1)))
    except re.error:  # a group name `re` would not take: `regex` reads the replacement when it is used
        return
    empty = stand_in.match("")
    assert empty is not None  # (every group of the stand-in matches the empty text)
    try:
        empty.expand(template)
    except (re.error, IndexError) as problem:
        raise SearchError(str(problem), "replace", getattr(problem, "pos", None)) from None
