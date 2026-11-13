"""Facets, kinds and slots: what a style property means, and where a style can be put (D303-D305, D312, D315).

A style stores its properties as one bag in CSS notation (``claudia_core.css`` checks the values). This module
says what those properties *are*:

* A **facet** is a named set of properties. Every property a style may set belongs to exactly one of the four:
  ``text`` (how characters look), ``paragraph`` (how a stretch of text is laid out), ``box`` (a rectangle around
  content) and ``outline`` (a shape's paint). A facet is what decides how a property reaches a renderer or a file
  format; the facet, not the notation, is the unit the rest of the suite talks about (D303).
* A style's **kind** says which facets it may hold: ``paragraph`` (text, paragraph and box — a composes
  Definition has a background and a border), ``box`` and ``outline`` (D305, D312).
* A **slot** is a place in a thing that reads a style: the box of a text box, the words of a cell. It reads only the
  facets it understands and offers only styles of its kind (D304). The :class:`SlotTable` says which slots every
  kind of thing has; :data:`SLOTS` is the table of what can be styled today.

The table is **open** (D315): a slide's background, a page or the parts of a diagram come later as one more row,
through :meth:`claudia_core.SlotTable.with_row`, without changing the facets, the kinds, or anything that reads
the table.

This module imports nothing from the rest of the kernel, so that ``claudia_core.css`` can build its checks from
it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Facet:
    """A named set of style properties: ``name`` and the CSS property names that belong to it, in the order a style
    lists them."""

    name: str
    properties: tuple[str, ...]


#: How characters look — font, size, weight, slant, decoration, colour and spacing.
TEXT_FACET = Facet(
    "text",
    (
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "text-decoration",
        "color",
        "letter-spacing",
        "word-spacing",
    ),
)
#: How a stretch of text is laid out — alignment, line height, the space around it, and whether its words may be
#: hyphenated at the end of a line (``hyphens``, CSS_VERSION 4, D912).
PARAGRAPH_FACET = Facet(
    "paragraph",
    ("text-align", "line-height", "margin-top", "margin-right", "margin-bottom", "margin-left", "hyphens"),
)
#: A rectangle around content — its background, padding, a border per side, and where its content sits in it.
BOX_FACET = Facet(
    "box",
    (
        "background-color",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "vertical-align",
        "white-space",
    ),
)
#: A shape's paint in the SVG vocabulary of D178 — fill, stroke and the stroke's width.
OUTLINE_FACET = Facet("outline", ("fill", "stroke", "stroke-width"))

#: The four facets, in the order the rest of the suite lists them.
FACETS: tuple[Facet, ...] = (TEXT_FACET, PARAGRAPH_FACET, BOX_FACET, OUTLINE_FACET)

_FACET_OF: dict[str, Facet] = {prop: facet for facet in FACETS for prop in facet.properties}
if len(_FACET_OF) != sum(len(facet.properties) for facet in FACETS):  # pragma: no cover - a mistake in this file
    raise RuntimeError("a style property is listed in two facets")

#: Every property a style may set, whichever facet it belongs to.
FACET_PROPERTIES: frozenset[str] = frozenset(_FACET_OF)

#: The kinds of style and the facets each may hold (D312).
KINDS: Mapping[str, tuple[Facet, ...]] = {
    "paragraph": (TEXT_FACET, PARAGRAPH_FACET, BOX_FACET),
    "box": (BOX_FACET,),
    "outline": (OUTLINE_FACET,),
}


def facet_of(prop: str) -> Facet:
    """The facet a property belongs to; ``KeyError`` for a property no style may set."""
    try:
        return _FACET_OF[prop]
    except KeyError:
        raise KeyError(f"“{prop}” is not a property a style can set") from None


def _facet_names(facets: Iterable[Facet]) -> str:
    names = [facet.name for facet in facets]
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else names[0]


def check_kind(kind: str, properties: Iterable[str]) -> None:
    """``ValueError`` unless every one of ``properties`` belongs to a facet a style of ``kind`` may hold; the
    sentence names every property that does not. Properties no style may set at all are ``claudia_core.css``'s
    to refuse, and are let through here."""
    facets = KINDS.get(kind)
    if facets is None:
        raise ValueError(f"A style's kind is one of {', '.join(KINDS)}, got {kind!r}")
    wrong = [prop for prop in properties if prop in _FACET_OF and _FACET_OF[prop] not in facets]
    if wrong:
        named = ", ".join(f"“{prop}”" for prop in wrong)
        raise ValueError(
            f"{named} {'is' if len(wrong) == 1 else 'are'} not a property of a {kind} style "
            f"(a {kind} style sets {_facet_names(facets)} properties)"
        )


@dataclass(frozen=True)
class Slot:
    """A place in a thing that reads a style: its ``name`` (``"box"``, ``"words"``), the facets it ``reads`` (and
    ignores the rest of), and its own ``kind`` — the kind of a style made for this slot alone. Which styles may be
    put into it is :func:`fits`'s answer, which is wider than the slot's own kind (D316)."""

    name: str
    reads: tuple[Facet, ...]
    kind: str

    def to_data(self) -> dict:
        """The plain-data form: ``{name, reads, kind, takes}`` with the facets by name; ``takes`` lists the kinds
        of style that fit the slot (:func:`fits`), so a client filters without a copy of the rule."""
        return {
            "name": self.name,
            "reads": [facet.name for facet in self.reads],
            "kind": self.kind,
            "takes": [kind for kind in KINDS if fits(kind, self)],
        }


def fits(kind: str, slot: Slot) -> bool:
    """Can a style of ``kind`` be put into ``slot``? Yes when the kind can hold every facet the slot reads (D316).

    So a ``box`` slot takes a box style *and* a paragraph style — a paragraph style may hold a box, and the slot
    reads only that part of it, which is how one named bundle fills both slots of a cell or a text box (D309,
    D311). A ``words`` slot takes only paragraph styles, an ``outline`` slot only outline styles. A slot that reads
    nothing (a picture's box) takes only styles of its own kind."""
    facets = KINDS.get(kind)
    if facets is None:
        return False
    if not slot.reads:
        return kind == slot.kind
    return all(facet in facets for facet in slot.reads)


def _check_row(thing: str, slots: tuple[Slot, ...]) -> None:
    if not slots:
        raise ValueError(f"“{thing}” has no slots: a thing that cannot be styled is left out of the table")
    names = [slot.name for slot in slots]
    if len(names) != len(set(names)):
        raise ValueError(f"“{thing}” names a slot twice")
    for slot in slots:
        allowed = KINDS.get(slot.kind)
        if allowed is None:
            raise ValueError(
                f"The slot “{thing}.{slot.name}” offers styles of the kind {slot.kind!r}, which is not a kind"
            )
        beyond = [facet for facet in slot.reads if facet not in allowed]
        if beyond:
            raise ValueError(
                f"The slot “{thing}.{slot.name}” reads {_facet_names(beyond)}, which a {slot.kind} style cannot hold"
            )


class SlotTable:
    """Which slots every kind of thing has. Immutable: :meth:`SlotTable.with_row` gives a new table with one more
    thing."""

    def __init__(self, rows: Mapping[str, Iterable[Slot]]):
        self._rows: dict[str, tuple[Slot, ...]] = {}
        for thing, slots in rows.items():
            row = tuple(slots)
            _check_row(thing, row)
            self._rows[thing] = row

    def things(self) -> list[str]:
        """The kinds of thing that can be styled, in the order of the table."""
        return list(self._rows)

    def slots_of(self, thing: str) -> tuple[Slot, ...]:
        """The slots of a kind of thing; ``KeyError`` for a thing the table does not have."""
        try:
            return self._rows[thing]
        except KeyError:
            raise KeyError(f"“{thing}” is not something a style can be put into") from None

    def slot(self, thing: str, name: str) -> Slot:
        """One slot of a kind of thing, by name; ``KeyError`` if it has no such slot."""
        for slot in self.slots_of(thing):
            if slot.name == name:
                return slot
        raise KeyError(f"“{thing}” has no slot “{name}”")

    def with_row(self, thing: str, slots: Iterable[Slot]) -> SlotTable:
        """A new table with ``thing`` and its slots added (D315): how a later kind of thing joins the suite."""
        if thing in self._rows:
            raise ValueError(f"“{thing}” is in the table already")
        return SlotTable({**self._rows, thing: tuple(slots)})

    def to_data(self) -> dict:
        """The facets, the kinds and the slots as plain data — what a client is sent, so it keeps no copy."""
        return {
            "facets": {facet.name: list(facet.properties) for facet in FACETS},
            "kinds": {kind: [facet.name for facet in facets] for kind, facets in KINDS.items()},
            "slots": {thing: [slot.to_data() for slot in slots] for thing, slots in self._rows.items()},
        }


_WORDS = (TEXT_FACET, PARAGRAPH_FACET)

#: Everything that can be styled today, and its slots (D304, D310, D311). A composes paragraph is one slot that reads
#: all three of a paragraph style's facets; a text box, a shape and a cell each have a container and words; a
#: picture's box reads nothing yet (it carries its own colours); a diagram draws itself and has a box around it.
SLOTS = SlotTable(
    {
        "paragraph": (Slot("paragraph", (TEXT_FACET, PARAGRAPH_FACET, BOX_FACET), "paragraph"),),
        "text": (Slot("box", (BOX_FACET,), "box"), Slot("words", _WORDS, "paragraph")),
        "shape": (Slot("outline", (OUTLINE_FACET,), "outline"), Slot("label", _WORDS, "paragraph")),
        "image": (Slot("box", (), "box"),),
        "diagram": (Slot("box", (BOX_FACET,), "box"),),
        "cell": (Slot("box", (BOX_FACET,), "box"), Slot("words", _WORDS, "paragraph")),
    }
)
