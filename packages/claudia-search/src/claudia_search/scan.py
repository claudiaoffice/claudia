"""Searching a document and planning a replacement, for any app (E5.15, D284-D286; CODE-18).

An app hands a search its texts as :class:`Text`: the text, the kind of text it is (computes: ``text``, ``formula``,
``value``) and *where* it is, ``at``. ``at`` is the app's own and opaque here: a small mapping of plain values that the
app can read back (computes: ``{"sheet", "row", "col"}``; a paragraph and an offset, or a slide and an object, for the
other apps). Everything a search answers names its place by that ``at``, and a client sends it back unchanged to say
which matches to leave alone. Nothing in this module knows sheets, paragraphs or slides.

Both :func:`scan` and :func:`plan` run until a *deadline* (a :func:`time.monotonic` time): once it passes they stop,
inside a pattern if need be, and say so (``timed_out``) with what they had found by then.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .engine import CompiledSearch, Match, SearchTimeout

Location = Mapping[str, Any]  # where a text is, in the app's own terms: plain values only (it goes over the wire)

MAX_LISTED = 2_000  # matches a search lists; the counts are of all of them
CONTEXT = 60  # characters of a text shown on each side of a match
MAX_SHOWN = 120  # characters of a match itself that are shown


def location_key(at: Location) -> str:
    """One string per place, the same for equal mappings whatever their order: for sets and dictionaries of places."""
    return json.dumps(at, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Text:
    """A text an app offers to a search: where it is, what kind of text it is, and the text."""

    at: Location
    kind: str
    text: str


@dataclass(frozen=True)
class Hit:
    """One match: where, the kind of text it is in, its number among the matches of that text, and where in it."""

    at: Location
    kind: str
    number: int
    start: int
    end: int
    kept: tuple[str, ...]
    after: str | None  # what the match would become; ``None`` if it is never replaced or there is no replacement
    text: str  # an excerpt of the text around the match
    excerpt_start: int  # the match inside ``text``
    excerpt_end: int
    clipped_before: bool  # the text goes on before ``text``
    clipped_after: bool  # and after it

    def to_data(self) -> dict:
        """The match as a client receives it."""
        return {
            "at": dict(self.at),
            "kind": self.kind,
            "number": self.number,
            "start": self.start,
            "end": self.end,
            "parts": list(self.kept),
            "after": self.after,
            "text": self.text,
            "excerpt": [self.excerpt_start, self.excerpt_end],
            "clipped": [self.clipped_before, self.clipped_after],
        }


@dataclass(frozen=True)
class LeftOut:
    """A text that looks like a match but was left out, and why (a condition's data, or ``{"kind": "filter"}``)."""

    at: Location
    kind: str
    why: dict

    def to_data(self) -> dict:
        """As a client receives it."""
        return {"at": dict(self.at), "kind": self.kind, "why": self.why}


@dataclass
class Scan:
    """What a search found: the matches (at most ``max_listed``), the texts left out, and how much there is."""

    matches: list[Hit] = field(default_factory=list)
    left_out: list[LeftOut] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)  # texts holding a match, by kind of text
    total: int = 0  # all matches, also those not listed
    truncated: bool = False  # more matches than are listed
    timed_out: bool = False  # the search was stopped before it had looked at everything


@dataclass(frozen=True)
class Change:
    """A text a replacement changes, from ``before`` to ``after``."""

    at: Location
    kind: str
    before: str
    after: str

    def to_data(self) -> dict:
        """As a client receives it."""
        return {"at": dict(self.at), "kind": self.kind, "before": self.before, "after": self.after}


@dataclass(frozen=True)
class Skip:
    """A text a replacement leaves alone, and why: ``reason`` is the app's (computes: ``locked``, with ``by`` the person
    who holds it; ``formula``; ``too_long``)."""

    at: Location
    kind: str
    reason: str
    by: str | None = None

    def to_data(self) -> dict:
        """As a client receives it."""
        return {"at": dict(self.at), "kind": self.kind, "reason": self.reason, "by": self.by}


@dataclass
class Plan:
    """What a replacement would do. ``timed_out``: the deadline passed before every text was looked at, so the plan is
    not the whole of it and must not be carried out."""

    changes: list[Change] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)
    timed_out: bool = False


# --------------------------------------------------------------------------------------------------------- looking
def scan(
    texts: Iterable[Text],
    search: CompiledSearch,
    *,
    deadline: float | None = None,
    replaceable: Collection[str] | None = None,
    max_listed: int = MAX_LISTED,
) -> Scan:
    """Where ``search`` finds something in ``texts``, in their order. ``replaceable`` names the kinds of text a
    replacement may change (``None``: all); a match in another kind has no ``after``. Stops when ``deadline`` passes
    (``timed_out``)."""
    result = Scan()
    try:
        for item in texts:
            found = search.matches(item.text, deadline)
            if not found:
                why = search.left_out(item.text, deadline)
                if why is not None:
                    result.left_out.append(LeftOut(item.at, item.kind, why))
                continue
            result.counts[item.kind] = result.counts.get(item.kind, 0) + 1
            result.total += len(found)
            changes = replaceable is None or item.kind in replaceable
            for number, match in enumerate(found):
                if len(result.matches) >= max_listed:
                    result.truncated = True
                    break
                result.matches.append(_hit(item, number, match, changes))
    except SearchTimeout:
        result.timed_out = True
    return result


def _hit(item: Text, number: int, match: Match, changes: bool) -> Hit:
    shown_end = min(match.end, match.start + MAX_SHOWN)
    first, last = max(0, match.start - CONTEXT), min(len(item.text), shown_end + CONTEXT)
    return Hit(
        item.at,
        item.kind,
        number,
        match.start,
        match.end,
        match.kept,
        match.after if changes else None,
        item.text[first:last],
        match.start - first,
        shown_end - first,
        first > 0,
        last < len(item.text),
    )


# ------------------------------------------------------------------------------------------------------- replacing
Refusal = Callable[[Text, str], "tuple[str, str | None] | None"]  # (text, after) -> (reason, by), or None: allowed


def plan(
    texts: Iterable[Text],
    search: CompiledSearch,
    *,
    leave: Iterable[tuple[Location, int | None]] = (),
    refuse: Refusal | None = None,
    deadline: float | None = None,
) -> Plan:
    """What replacing would do in ``texts``, without doing it. ``leave`` names matches a person wants to keep, as
    ``(at, number)``; ``number`` ``None`` keeps every match at that place. ``refuse`` is the app's say on a change
    (``(reason, by)`` to skip it). Stops when ``deadline`` passes (``timed_out``).

    ``SearchError`` when the search has no replacement."""
    kept = _leave(leave)
    result = Plan()
    try:
        for item in texts:
            skip = kept.get(location_key(item.at), set())
            if skip is None:
                continue
            after = search.replaced(item.text, skip, deadline)
            if after == item.text:
                continue
            refusal = refuse(item, after) if refuse is not None else None
            if refusal is not None:
                result.skipped.append(Skip(item.at, item.kind, *refusal))
            else:
                result.changes.append(Change(item.at, item.kind, item.text, after))
    except SearchTimeout:
        result.timed_out = True
    return result


def _leave(items: Iterable[tuple[Location, int | None]]) -> dict[str, set[int] | None]:
    leave: dict[str, set[int] | None] = {}
    for at, number in items:
        key = location_key(at)
        if number is None:
            leave[key] = None
        elif (already := leave.get(key, set())) is not None:
            leave[key] = {*already, number}
    return leave


__all__ = [
    "CONTEXT",
    "MAX_LISTED",
    "MAX_SHOWN",
    "Change",
    "Hit",
    "LeftOut",
    "Location",
    "Plan",
    "Refusal",
    "Scan",
    "Skip",
    "Text",
    "location_key",
    "plan",
    "scan",
]
