"""Search and replace in a text (E9.28, D284-D289): what is looked at, where, and what a replacement changes.

``claudia_search`` runs a search over texts that come with their place and knows no app. This module is composes'
part of it: which texts a document offers, where they are, and how a replacement is stored.

A search looks in one or more *kinds* of text:

``text``         a paragraph in a body style (and quotes, lists, and every style that is neither of the two below)
``heading``      a paragraph in a title or heading style, or in one that is based on such a style
``remark``       a paragraph in the remark style, or in one based on it
``object``       the words in an object that floats over the text: a text box's paragraph, a shape's label
``description``  what an object says to somebody who cannot see it (BITV 1.1.1)

All of them are stored text and may be replaced. A place (``at``) is ``{"block"}`` for a paragraph, with ``"offset"``
when only the part of it from there on was searched (a selection starts or ends in it: the matches count from there),
and ``{"block", "object", "source"}`` for the words or the description of an object, ``block`` being the paragraph it
hangs from (so that a client can take a person there).

A search covers the whole text, one *section* (``{"section": paragraph}``: from the heading the paragraph is under to
the next heading of the same or a higher level, subsections included) or a selection
(``{"range": {"from": {block, offset}, "to": {block, offset}}}``).

A replacement is planned first (:func:`plan_replacement`), then made by :func:`replace_command` as one command that
stores the changed stretches as typing and deleting: whoever wrote the words around a match stays their author, and
whoever replaced is the author of what they put in. A paragraph somebody else holds a zone in, where a match lies in
that zone, is skipped and the holder named; so is a paragraph that has been typed into since the person looked.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from claudia_core import Batch, Command, Region, edit_object_text, object_texts
from claudia_search import CompiledSearch, Location, Plan, Scan, SearchError, Skip, Text, plan, scan

from .commands import DeleteText, InsertText
from .model import Block, TextModel
from .region import TextRange

KINDS = ("text", "heading", "remark", "object", "description")
EXTRA_PARTS: Mapping[str, str] = {
    # A word: letters and digits that are not part of a longer run of them
    "word": r"(?<!\w)\w+(?!\w)",
}

_HEADING_LEVELS = {"heading-1": 1, "heading-2": 2}
_HEADINGS = frozenset({"title", *_HEADING_LEVELS})
_REMARK = "remark"
_OBJECT_KIND = {"box": "object", "label": "object", "description": "description"}

Conflicts = Callable[[Sequence[Region]], Sequence[tuple[str, Region]]]  # the locks of other people on these regions


def block_at(block: str, offset: int | None = None) -> Location:
    """Where a paragraph is, as every answer of a search names it; ``offset`` when only the paragraph from there on
    was searched."""
    return {"block": block} if offset is None else {"block": block, "offset": offset}


def object_at(block: str, object_id: str, source: str) -> Location:
    """Where the words (``box``, ``label``) or the description of an object are, and the paragraph it hangs from."""
    return {"block": block, "object": object_id, "source": source}


def block_of(at: Location) -> tuple[str, int]:
    """``(paragraph, offset)`` of a place a client sent back; ``ValueError`` if it is not a paragraph's."""
    keys = set(at) if isinstance(at, Mapping) else set()
    offset = at.get("offset", 0) if keys <= {"block", "offset"} else None
    if "block" not in keys or not isinstance(at["block"], str) or offset is None or not _natural(offset):
        raise ValueError("a place in a paragraph is {block} or {block, offset}")
    return at["block"], int(offset)


def object_of(at: Location) -> tuple[str, str, str]:
    """``(paragraph, object, source)`` of a place a client sent back; ``ValueError`` if it is not an object's."""
    ok = isinstance(at, Mapping) and set(at) == {"block", "object", "source"}
    if not ok or not all(isinstance(at[k], str) for k in at) or at["source"] not in _OBJECT_KIND:
        raise ValueError("a place in an object is {block, object, source}, the source being box, label or description")
    return at["block"], at["object"], at["source"]


def _natural(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


# --------------------------------------------------------------------------------------------------------- looking
def kind_of(model: TextModel, block: Block) -> str:
    """``heading``, ``remark`` or ``text``: what a paragraph is by its style and the styles that style is based on."""
    ids = _chain(model, block.style)
    if _HEADINGS.intersection(ids):
        return "heading"
    return "remark" if _REMARK in ids else "text"


def _chain(model: TextModel, style: str) -> list[str]:
    try:
        return [s.id for s in model.styles.chain(style)]
    except (KeyError, ValueError):
        return [style]


def _level(model: TextModel, block: Block) -> int | None:
    """The level of a section heading (1, 2), or ``None`` for a paragraph that starts no section."""
    for style_id in reversed(_chain(model, block.style)):  # the style itself first, then what it is based on
        if style_id in _HEADING_LEVELS:
            return _HEADING_LEVELS[style_id]
    return None


def _check_kinds(kinds: Sequence[str]) -> None:
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise ValueError(f"cannot look in {unknown[0]!r}: choose from {', '.join(KINDS)}")


def _block_index(model: TextModel, block_id: str) -> int:
    try:
        return model.index_of(block_id)
    except KeyError:
        raise ValueError(f"no such paragraph: {block_id!r}") from None


Stretch = tuple[Block, int, int | None, bool]  # paragraph, first character searched, end (None: its end), partial?


def _stretches(model: TextModel, scope: Mapping | None) -> list[Stretch]:
    """The paragraphs a scope covers, and for a selection which part of its first and last."""
    blocks = model.blocks
    if not scope:
        return [(b, 0, None, False) for b in blocks]
    if set(scope) == {"section"}:
        return [(b, 0, None, False) for b in _section(model, scope["section"])]
    if set(scope) == {"range"} and isinstance(scope["range"], Mapping):
        return _selection(model, scope["range"])
    raise ValueError("a scope is {section: paragraph} or {range: {from, to}}")


def _section(model: TextModel, block_id: str) -> list[Block]:
    blocks = model.blocks
    here = _block_index(model, block_id)
    start, level = 0, None
    for index in range(here, -1, -1):  # the heading this paragraph is under (or is)
        level = _level(model, blocks[index])
        if level is not None:
            start = index
            break
    end = len(blocks)
    for index in range(start + 1, len(blocks)):
        after = _level(model, blocks[index])
        if after is not None and (level is None or after <= level):
            end = index
            break
        if level is None and after is not None:
            end = index
            break
    if level is None:  # before the first heading: up to it
        end = next((i for i, b in enumerate(blocks) if _level(model, b) is not None), len(blocks))
    return blocks[start:end]


def _selection(model: TextModel, spec: Mapping) -> list[Stretch]:
    ends = []
    for key in ("from", "to"):
        end = spec.get(key)
        if not isinstance(end, Mapping) or not isinstance(end.get("block"), str) or not _natural(end.get("offset")):
            raise ValueError("a selection is {from: {block, offset}, to: {block, offset}}")
        ends.append((_block_index(model, end["block"]), end["offset"]))
    first, last = sorted(ends)
    stretches: list[Stretch] = []
    for index in range(first[0], last[0] + 1):
        block = model.blocks[index]
        start = first[1] if index == first[0] else 0
        stop = last[1] if index == last[0] else None
        stretches.append((block, start, stop, index in (first[0], last[0])))
    return stretches


def text_texts(model: TextModel, kinds: Sequence[str] = ("text",), scope: Mapping | None = None) -> Iterator[Text]:
    """What a text offers a search: the ``kinds`` of text, in the scope (``None``: the whole text), paragraph by
    paragraph, each paragraph followed by the objects that hang from it. ``ValueError`` for a kind, a paragraph or a
    scope that does not exist."""
    _check_kinds(kinds)
    wanted = set(kinds)
    sources = [s for s, kind in _OBJECT_KIND.items() if kind in wanted]
    return _texts(model, wanted, sources, _stretches(model, scope))


def _texts(model: TextModel, wanted: set[str], sources: list[str], stretches: list[Stretch]) -> Iterator[Text]:
    for block, start, stop, partial in stretches:
        kind = kind_of(model, block)
        text = block.text[start:stop]
        if kind in wanted and text:
            yield Text(block_at(block.id, start if partial else None), kind, text)
        if not sources:
            continue
        for item in object_texts(model, [block.id], sources):
            offset = model.get_object(item.object_id).anchor.offset
            if offset < start or (stop is not None and offset > stop):
                continue  # hangs from a place outside the selection
            yield Text(object_at(block.id, item.object_id, item.source), _OBJECT_KIND[item.source], item.text)


def scan_text(
    model: TextModel,
    search: CompiledSearch,
    *,
    kinds: Sequence[str] = ("text",),
    scope: Mapping | None = None,
    deadline: float | None = None,
) -> Scan:
    """Where ``search`` finds something in the text (see :func:`text_texts`), until ``deadline`` (a
    :func:`time.monotonic` time; then the answer says ``timed_out``). ``counts`` is by kind, each counting texts."""
    found = scan(text_texts(model, kinds, scope), search, deadline=deadline)
    found.counts = {kind: found.counts.get(kind, 0) for kind in KINDS}
    return found


# ------------------------------------------------------------------------------------------------------- replacing
def plan_replacement(
    model: TextModel,
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
    number)`` or ``(place, number, what it said)``; ``conflicts`` says which locks other people hold on regions (a
    paragraph with a match inside somebody's zone, and an object somebody has selected, are skipped and the holder
    named); ``max_length`` is the longest text a paragraph or object text may get. A plan that ran out of time before
    ``deadline`` says ``timed_out``.

    ``SearchError`` when the search has no replacement."""

    def too_long(item: Text, after: str) -> tuple[str, str | None] | None:
        return ("too_long", None) if max_length is not None and len(after) > max_length else None

    made = plan(text_texts(model, kinds, scope), search, leave=leave, refuse=too_long, deadline=deadline)
    kept = []
    for change in made.changes:
        owner = _holder(model, change.at, change.edits, conflicts)
        if owner is None:
            kept.append(change)
        else:
            made.skipped.append(Skip(change.at, change.kind, "locked", owner))
    made.changes = kept
    return made


def _holder(model: TextModel, at: Location, edits: Sequence, conflicts: Conflicts) -> str | None:
    """Who holds what a change touches, if somebody else does."""
    regions: list[Region]
    if "object" in at:
        regions = list(model.selection_of(object_of(at)[1]))
    else:
        block, origin = block_of(at)
        regions = [TextRange(block, origin + e.start, origin + max(e.end, e.start + 1)) for e in edits]
    held = conflicts(regions) if regions else []
    return held[0][0] if held else None


def replace_command(model: TextModel, made: Plan, author: str | None) -> Command | None:
    """The one command that makes the plan, from steps that type and delete (so the authors of what stays are kept)
    and rewrite object texts. ``None`` when nothing changes."""
    steps: list[Command] = []
    for change in made.changes:
        edits = [e for e in change.edits if e.before != e.after]
        if "object" in change.at:
            _, object_id, source = object_of(change.at)
            steps.append(edit_object_text(model, object_id, source, [(e.start, e.end, e.after) for e in edits], author))
            continue
        block, origin = block_of(change.at)
        for e in sorted(edits, key=lambda e: e.start, reverse=True):  # from the end, so offsets in front still hold
            if e.end > e.start:
                steps.append(DeleteText(block, origin + e.start, e.end - e.start))
            if e.after:
                steps.append(InsertText(block, origin + e.start, e.after))
    if not steps:
        return None
    count = len(made.changes)
    return Batch(tuple(steps), f"Replace in {count} text{'' if count == 1 else 's'}")


__all__ = [
    "EXTRA_PARTS",
    "KINDS",
    "SearchError",
    "block_at",
    "block_of",
    "kind_of",
    "object_at",
    "object_of",
    "plan_replacement",
    "replace_command",
    "scan_text",
    "text_texts",
]
