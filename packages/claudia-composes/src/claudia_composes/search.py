"""Search and replace in a text (E9.28, D284-D289): what is looked at, where, and what a replacement changes.

``claudia_search`` runs a search over texts that come with their place and knows no app. This module is composes'
part of it: which texts a document offers, where they are, and how a replacement is stored.

A search looks in one or more *kinds* of text:

``text``         a paragraph in a body style (and quotes, lists, and every style that is neither of the two below)
``heading``      a paragraph in a title or heading style, or in one that is based on such a style
``remark``       a paragraph in the remark style, or in one based on it
``object``       the words in an object that floats over the text: a text box's paragraph, a shape's label
``description``  what an object says to somebody who cannot see it (BITV 1.1.1)
``table``        the words in the boxes of a table (D1210), row by row; a box a merge covers has none

All of them are stored text and may be replaced. A place (``at``) is ``{"paragraph"}`` for a paragraph, with
``"offset"`` when only the part of it from there on was searched (a selection starts or ends in it: the matches count
from there), ``{"paragraph", "object", "source"}`` for the words or the description of an object and ``{"paragraph",
"table", "row", "col"}`` for a box of a table, ``paragraph`` being the paragraph the object hangs from (so that a client
can take a person there).

A search covers the whole text, one *section* (``{"section": paragraph}``: from the heading the paragraph is under to
the next heading of the same or a higher level, subsections included) or a selection
(``{"range": {"from": {paragraph, offset}, "to": {paragraph, offset}}}``).

A replacement is planned first (:func:`plan_replacement`), then made by :func:`replace_command` as one command that
stores the changed stretches as typing and deleting: whoever wrote the words around a match stays their author, and
whoever replaced is the author of what they put in. A paragraph somebody else holds a zone in, where a match lies in
that zone, is skipped and the holder named; so is a paragraph that has been typed into since the person looked.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from claudia_core import Batch, Command, Region, edit_object_text, entry_id, object_texts
from claudia_search import CompiledSearch, Location, Plan, Scan, SearchError, Skip, Text, plan, scan

from .commands import DeleteText, InsertText
from .model import Paragraph, TextModel
from .region import TextRange

KINDS = ("text", "heading", "remark", "object", "description", "table")
EXTRA_PARTS: Mapping[str, str] = {
    # A word: letters and digits that are not part of a longer run of them
    "word": r"(?<!\w)\w+(?!\w)",
}

_REMARK = "remark"
_OBJECT_KIND = {"box": "object", "label": "object", "description": "description"}

Conflicts = Callable[[Sequence[Region]], Sequence[tuple[str, Region]]]  # the locks of other people on these regions


def paragraph_at(paragraph: str, offset: int | None = None) -> Location:
    """Where a paragraph is, as every answer of a search names it; ``offset`` when only the paragraph from there on
    was searched."""
    return {"paragraph": paragraph} if offset is None else {"paragraph": paragraph, "offset": offset}


def object_at(paragraph: str, object_id: str, source: str) -> Location:
    """Where the words (``box``, ``label``) or the description of an object are, and the paragraph it hangs from."""
    return {"paragraph": paragraph, "object": object_id, "source": source}


def paragraph_of(at: Location) -> tuple[str, int]:
    """``(paragraph, offset)`` of a place a client sent back; ``ValueError`` if it is not a paragraph's."""
    keys = set(at) if isinstance(at, Mapping) else set()
    offset = at.get("offset", 0) if keys <= {"paragraph", "offset"} else None
    if "paragraph" not in keys or not isinstance(at["paragraph"], str) or offset is None or not _natural(offset):
        raise ValueError("a place in a paragraph is {paragraph} or {paragraph, offset}")
    return at["paragraph"], int(offset)


def object_of(at: Location) -> tuple[str, str, str]:
    """``(paragraph, object, source)`` of a place a client sent back; ``ValueError`` if it is not an object's."""
    ok = isinstance(at, Mapping) and set(at) == {"paragraph", "object", "source"}
    if not ok or not all(isinstance(at[k], str) for k in at) or at["source"] not in _OBJECT_KIND:
        raise ValueError(
            "a place in an object is {paragraph, object, source}, the source being box, label or description"
        )
    return at["paragraph"], at["object"], at["source"]


def table_at(paragraph: str, table: str, row: str, col: str) -> Location:
    """Where a box of a table is, and the paragraph the table hangs from."""
    return {"paragraph": paragraph, "table": table, "row": row, "col": col}


def table_of(at: Location) -> tuple[str, str, str, str]:
    """``(paragraph, table, row, column)`` of a place a client sent back; ``ValueError`` if it is not a box's."""
    ok = isinstance(at, Mapping) and set(at) == {"paragraph", "table", "row", "col"}
    if not ok or not all(isinstance(at[k], str) for k in at):
        raise ValueError("a place in a box of a table is {paragraph, table, row, col}")
    return at["paragraph"], at["table"], at["row"], at["col"]


def _natural(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


# --------------------------------------------------------------------------------------------------------- looking
def kind_of(model: TextModel, paragraph: Paragraph) -> str:
    """``heading``, ``remark`` or ``text``: what a paragraph is by its style and the styles that style is based on."""
    if model.heading_level(paragraph) is not None:
        return "heading"
    return "remark" if _REMARK in _chain(model, paragraph.style) else "text"


def _chain(model: TextModel, style: str) -> list[str]:
    try:
        return [s.id for s in model.styles.chain(style)]
    except (KeyError, ValueError):
        return [style]


def _level(model: TextModel, paragraph: Paragraph) -> int | None:
    """The level of a section heading (1 to 9), or ``None`` for a paragraph that starts no section (the title, which
    names the whole text, starts none)."""
    level = model.heading_level(paragraph)
    return level if level else None


def _check_kinds(kinds: Sequence[str]) -> None:
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        raise ValueError(f"cannot look in {unknown[0]!r}: choose from {', '.join(KINDS)}")


def _paragraph_index(model: TextModel, paragraph_id: str) -> int:
    try:
        return model.index_of(paragraph_id)
    except KeyError:
        raise ValueError(f"no such paragraph: {paragraph_id!r}") from None


Stretch = tuple[Paragraph, int, int | None, bool]  # paragraph, first character searched, end (None: its end), partial?


def _stretches(model: TextModel, scope: Mapping | None) -> list[Stretch]:
    """The paragraphs a scope covers, and for a selection which part of its first and last."""
    paragraphs = model.paragraphs
    if not scope:
        return [(b, 0, None, False) for b in paragraphs]
    if set(scope) == {"section"}:
        return [(b, 0, None, False) for b in _section(model, scope["section"])]
    if set(scope) == {"range"} and isinstance(scope["range"], Mapping):
        return _selection(model, scope["range"])
    raise ValueError("a scope is {section: paragraph} or {range: {from, to}}")


def _section(model: TextModel, paragraph_id: str) -> list[Paragraph]:
    paragraphs = model.paragraphs
    here = _paragraph_index(model, paragraph_id)
    start, level = 0, None
    for index in range(here, -1, -1):  # the heading this paragraph is under (or is)
        level = _level(model, paragraphs[index])
        if level is not None:
            start = index
            break
    end = len(paragraphs)
    for index in range(start + 1, len(paragraphs)):
        after = _level(model, paragraphs[index])
        if after is not None and (level is None or after <= level):
            end = index
            break
        if level is None and after is not None:
            end = index
            break
    if level is None:  # before the first heading: up to it
        end = next((i for i, b in enumerate(paragraphs) if _level(model, b) is not None), len(paragraphs))
    return paragraphs[start:end]


def _selection(model: TextModel, spec: Mapping) -> list[Stretch]:
    ends = []
    for key in ("from", "to"):
        end = spec.get(key)
        if not isinstance(end, Mapping) or not isinstance(end.get("paragraph"), str) or not _natural(end.get("offset")):
            raise ValueError("a selection is {from: {paragraph, offset}, to: {paragraph, offset}}")
        ends.append((_paragraph_index(model, end["paragraph"]), end["offset"]))
    first, last = sorted(ends)
    stretches: list[Stretch] = []
    for index in range(first[0], last[0] + 1):
        paragraph = model.paragraphs[index]
        start = first[1] if index == first[0] else 0
        stop = last[1] if index == last[0] else None
        stretches.append((paragraph, start, stop, index in (first[0], last[0])))
    return stretches


def text_texts(model: TextModel, kinds: Sequence[str] = ("text",), scope: Mapping | None = None) -> Iterator[Text]:
    """What a text offers a search: the ``kinds`` of text, in the scope (``None``: the whole text), paragraph by
    paragraph, each paragraph followed by the objects that hang from it. ``ValueError`` for a kind, a paragraph or a
    scope that does not exist."""
    _check_kinds(kinds)
    wanted = set(kinds)
    sources = [s for s, kind in _OBJECT_KIND.items() if kind in wanted]
    return _texts(model, wanted, sources, _stretches(model, scope))


def _box_texts(model: TextModel, paragraph: Paragraph, start: int, stop: int | None) -> Iterator[Text]:
    """The words of the boxes of the tables that hang from ``paragraph`` (from a place inside the stretch), by row."""
    for shown in model.objects_on(paragraph.id):
        table_id = shown.body.table
        if table_id is None or table_id not in model.tables:
            continue
        if shown.anchor.offset < start or (stop is not None and shown.anchor.offset > stop):
            continue  # hangs from a place outside the selection
        definition = model.tables[table_id]
        for row in definition.rows:
            for col in definition.column_ids():
                words = definition.paragraph(row, col).text
                if words and not definition.covered(row, col):
                    yield Text(table_at(paragraph.id, table_id, row, col), "table", words)


def _texts(model: TextModel, wanted: set[str], sources: list[str], stretches: list[Stretch]) -> Iterator[Text]:
    for paragraph, start, stop, partial in stretches:
        kind = kind_of(model, paragraph)
        text = paragraph.text[start:stop]
        if kind in wanted and text:
            yield Text(paragraph_at(paragraph.id, start if partial else None), kind, text)
        if "table" in wanted:
            yield from _box_texts(model, paragraph, start, stop)
        if not sources:
            continue
        for item in object_texts(model, [paragraph.id], sources):
            offset = model.get_object(item.object_id).anchor.offset
            if offset < start or (stop is not None and offset > stop):
                continue  # hangs from a place outside the selection
            yield Text(object_at(paragraph.id, item.object_id, item.source), _OBJECT_KIND[item.source], item.text)


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
    if "table" in at:
        _, table, row, col = table_of(at)
        regions = list(model.text_regions(entry_id(table, row, col), 0, 1))
    elif "object" in at:
        regions = list(model.selection_of(object_of(at)[1]))
    else:
        paragraph, origin = paragraph_of(at)
        regions = [TextRange(paragraph, origin + e.start, origin + max(e.end, e.start + 1)) for e in edits]
    held = conflicts(regions) if regions else []
    return held[0][0] if held else None


def _box_steps(box: str, edits: Sequence) -> list[Command]:
    """The typing and deleting that make ``edits`` in one box, from the end; a box is one line, so a line break in what
    is put in is a space (D1212)."""
    steps: list[Command] = []
    for e in sorted(edits, key=lambda e: e.start, reverse=True):
        if e.end > e.start:
            steps.append(DeleteText(box, e.start, e.end - e.start))
        line = " ".join(e.after.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
        if line:
            steps.append(InsertText(box, e.start, line))
    return steps


def replace_command(model: TextModel, made: Plan, author: str | None) -> Command | None:
    """The one command that makes the plan, from steps that type and delete (so the authors of what stays are kept)
    and rewrite object texts. ``None`` when nothing changes."""
    steps: list[Command] = []
    for change in made.changes:
        edits = [e for e in change.edits if e.before != e.after]
        if "table" in change.at:
            _, table, row, col = table_of(change.at)
            steps += _box_steps(entry_id(table, row, col), [e for e in change.edits if e.before != e.after])
            continue
        if "object" in change.at:
            _, object_id, source = object_of(change.at)
            steps.append(edit_object_text(model, object_id, source, [(e.start, e.end, e.after) for e in edits], author))
            continue
        paragraph, origin = paragraph_of(change.at)
        for e in sorted(edits, key=lambda e: e.start, reverse=True):  # from the end, so offsets in front still hold
            if e.end > e.start:
                steps.append(DeleteText(paragraph, origin + e.start, e.end - e.start))
            if e.after:
                steps.append(InsertText(paragraph, origin + e.start, e.after))
    if not steps:
        return None
    count = len(made.changes)
    return Batch(tuple(steps), f"Replace in {count} text{'' if count == 1 else 's'}")


__all__ = [
    "EXTRA_PARTS",
    "KINDS",
    "SearchError",
    "paragraph_at",
    "paragraph_of",
    "kind_of",
    "object_at",
    "object_of",
    "plan_replacement",
    "replace_command",
    "scan_text",
    "table_at",
    "table_of",
    "text_texts",
]
