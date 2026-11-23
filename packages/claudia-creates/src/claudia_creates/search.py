"""Search and replace in a presentation (E10.19, D284-D289): what is looked at, where, and what a replacement changes.

``claudia_search`` runs a search over texts that come with their place and knows no app. This module is creates'
part of it: which texts a presentation offers, where they are, and how a replacement is stored.

A search looks in one or more *kinds* of text:

``text``         the words in a text box
``label``        the words in a shape (its label)
``notes``        the speaker notes of a slide, as written in Markdown (what is searched is what was typed, marks
                 included)
``description``  what an object says to somebody who cannot see it (BITV 1.1.1)

All of them are stored text and may be replaced. A place (``at``) is ``{"slide", "object", "source"}`` for the words
(``box``, ``label``) or the description of an object on a slide, and ``{"slide", "source": "notes"}`` for notes.

A search covers every slide or one (``{"slide": id}``, "this slide").

A replacement is planned first (:func:`plan_replacement`), then made by :func:`replace_command` as one command that
stores the texts as they will be: the words around a match keep whoever wrote them, and whoever replaced is the author
of what they put in. An object somebody has selected is skipped and the holder named, as is a text that has been
typed into since the person looked. Notes belong to no selection and are never locked.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from claudia_core import Batch, Command, Region, edit_object_text, object_texts
from claudia_search import CompiledSearch, Location, Plan, Scan, SearchError, Skip, Text, apply_edits, plan, scan

from .commands import SetSlideNotes
from .model import MAX_NOTES_LENGTH, SlideModel

KINDS = ("text", "label", "notes", "description")
EXTRA_PARTS: Mapping[str, str] = {
    # A word: letters and digits that are not part of a longer run of them
    "word": r"(?<!\w)\w+(?!\w)",
}

NOTES = "notes"
_OBJECT_SOURCES = {"text": "box", "label": "label", "description": "description"}  # kind -> the object's source
_KIND_OF = {"box": "text", "label": "label", "description": "description"}  # source -> kind

Conflicts = Callable[[Sequence[Region]], Sequence[tuple[str, Region]]]  # the locks of other people on these regions


def object_at(slide: str, object_id: str, source: str) -> Location:
    """Where the words (``box``, ``label``) or the description of an object are."""
    return {"slide": slide, "object": object_id, "source": source}


def notes_at(slide: str) -> Location:
    """Where the speaker notes of a slide are."""
    return {"slide": slide, "source": NOTES}


def place_of(at: Location) -> Location:
    """A place a client sent back, in its canonical form; ``ValueError`` if it is not one of a presentation's."""
    ok = isinstance(at, Mapping) and all(isinstance(v, str) for v in at.values())
    if ok and set(at) == {"slide", "source"} and at["source"] == NOTES:
        return notes_at(at["slide"])
    if ok and set(at) == {"slide", "object", "source"} and at["source"] in _KIND_OF:
        return object_at(at["slide"], at["object"], at["source"])
    raise ValueError("a place in a presentation is {slide, object, source} or {slide, source: notes}")


# --------------------------------------------------------------------------------------------------------- looking
def _check_kinds(kinds: Sequence[str]) -> None:
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise ValueError(f"cannot look in {unknown[0]!r}: choose from {', '.join(KINDS)}")


def _slides(model: SlideModel, scope: Mapping | None) -> list[str]:
    if not scope:
        return list(model.order)
    if set(scope) != {"slide"}:
        raise ValueError("a scope is {slide: id}, or nothing for every slide")
    if scope["slide"] not in model.order:
        raise ValueError(f"no such slide: {scope['slide']!r}")
    return [scope["slide"]]


def slide_texts(model: SlideModel, kinds: Sequence[str] = ("text",), scope: Mapping | None = None) -> Iterator[Text]:
    """What a presentation offers a search: the ``kinds`` of text, slide by slide (objects back to front, then the
    notes), on one slide or on all. ``ValueError`` for a kind, a slide or a scope that does not exist."""
    _check_kinds(kinds)
    slides = _slides(model, scope)
    sources = [source for kind, source in _OBJECT_SOURCES.items() if kind in kinds]
    return _texts(model, slides, sources, NOTES in kinds)


def _texts(model: SlideModel, slides: list[str], sources: list[str], with_notes: bool) -> Iterator[Text]:
    for slide in slides:
        for item in object_texts(model, [slide], sources):
            yield Text(object_at(slide, item.object_id, item.source), _KIND_OF[item.source], item.text)
        if with_notes and (notes := model.notes_of(slide)):
            yield Text(notes_at(slide), NOTES, notes)


def scan_slides(
    model: SlideModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    scope: Mapping | None = None,
    deadline: float | None = None,
) -> Scan:
    """Where ``search`` finds something in the presentation (see :func:`slide_texts`), until ``deadline`` (a
    :func:`time.monotonic` time; then the answer says ``timed_out``). ``counts`` is by kind, each counting texts."""
    found = scan(slide_texts(model, kinds, scope), search, deadline=deadline)
    found.counts = {kind: found.counts.get(kind, 0) for kind in KINDS}
    return found


# ------------------------------------------------------------------------------------------------------- replacing
def plan_replacement(
    model: SlideModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    scope: Mapping | None = None,
    leave: Iterable[tuple[Location, int | None] | tuple[Location, int | None, str | None]] = (),
    conflicts: Conflicts,
    max_length: int | None = None,
    deadline: float | None = None,
) -> Plan:
    """What replacing would do, without doing it. ``leave`` names matches a person wants to keep, as ``(place,
    number)`` or ``(place, number, what it said)``; ``conflicts`` says which locks other people hold on regions (an
    object somebody has selected is skipped, and the holder named); ``max_length`` is the longest text an object may
    get (notes have their own limit). A plan that ran out of time before ``deadline`` says ``timed_out``.

    ``SearchError`` when the search has no replacement."""

    def too_long(item: Text, after: str) -> tuple[str, str | None] | None:
        limit = MAX_NOTES_LENGTH if item.kind == NOTES else max_length
        return ("too_long", None) if limit is not None and len(after) > limit else None

    made = plan(slide_texts(model, kinds, scope), search, leave=leave, refuse=too_long, deadline=deadline)
    kept = []
    for change in made.changes:
        owner = _holder(model, change.at, conflicts)
        if owner is None:
            kept.append(change)
        else:
            made.skipped.append(Skip(change.at, change.kind, "locked", owner))
    made.changes = kept
    return made


def _holder(model: SlideModel, at: Location, conflicts: Conflicts) -> str | None:
    """Who holds an object, if somebody else does (notes are nobody's to hold)."""
    if at["source"] == NOTES:
        return None
    held = conflicts(list(model.selection_of(at["object"])))
    return held[0][0] if held else None


def replace_command(model: SlideModel, made: Plan, author: str | None) -> Command | None:
    """The one command that makes the plan: each object's text stored as it will be (the authors of what stays
    are kept), each slide's notes as they will be. ``None`` when nothing changes."""
    steps: list[Command] = []
    for change in made.changes:
        edits = [e for e in change.edits if e.before != e.after]
        if not edits:
            continue
        if change.at["source"] == NOTES:
            steps.append(SetSlideNotes(change.at["slide"], apply_edits(change.before, edits)))
        else:
            spans = [(e.start, e.end, e.after) for e in edits]
            steps.append(edit_object_text(model, change.at["object"], change.at["source"], spans, author))
    if not steps:
        return None
    count = len(steps)
    return Batch(tuple(steps), f"Replace in {count} text{'' if count == 1 else 's'}")


__all__ = [
    "EXTRA_PARTS",
    "KINDS",
    "SearchError",
    "notes_at",
    "object_at",
    "place_of",
    "plan_replacement",
    "replace_command",
    "scan_slides",
    "slide_texts",
]
