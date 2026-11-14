"""The texts of objects, for a search (E9.28, E10.19): what an object says, and how a replacement of it is made.

An object carries two texts, the same in every app: the *words* in it (a text box's paragraph, a shape's label) and
its *description*, what it says to somebody who cannot see it (BITV 1.1.1). Both are stored contents, so both may be
replaced. This module offers them to a search as plain tuples and builds the command that stores an edit, so that
composes and creates search and replace in objects the same way and neither repeats it. It knows no pattern and no
slide or paragraph: the app names the containers (a slide, a paragraph) and what it calls each kind of text.

A replacement keeps what it does not touch: a paragraph's words are rewritten with :func:`replace_spans`, so who
wrote the rest of them, and the style, stay as they were; whoever replaced is the author of what they put in.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .commands import Command
from .objects import DescribeObject, ObjectModel, SetParagraph
from .paragraphs import replace_spans

#: What a text of an object is: the words of a text box, the label of any other object, or the description.
BOX = "box"
LABEL = "label"
DESCRIPTION = "description"
SOURCES = (BOX, LABEL, DESCRIPTION)


@dataclass(frozen=True)
class ObjectText:
    """One text of one object: which, in which container (a slide, a paragraph), what kind of text, and the text."""

    object_id: str
    container: str
    source: str
    text: str


def object_texts(
    model: ObjectModel, containers: Iterable[str], sources: Iterable[str] = SOURCES
) -> Iterator[ObjectText]:
    """The texts the objects of these containers have, container by container (in the order given) and object by
    object (back to front, as the model stacks them); an empty text is not offered. ``ValueError`` for a source that
    does not exist."""
    wanted = set(sources)
    unknown = wanted - set(SOURCES)
    if unknown:
        raise ValueError(f"an object has {', '.join(SOURCES)}; not {sorted(unknown)[0]!r}")
    for container in containers:
        for obj in model.objects_on(container):
            words = obj.body.paragraph
            source = BOX if obj.body.kind == "text" else LABEL
            if words is not None and words.text and source in wanted:
                yield ObjectText(obj.id, container, source, words.text)
            if DESCRIPTION in wanted and obj.body.description:
                yield ObjectText(obj.id, container, DESCRIPTION, obj.body.description)


def edit_object_text(
    model: ObjectModel, object_id: str, source: str, edits: Iterable[tuple[int, int, str]], author: str | None
) -> Command:
    """The command that stores ``edits`` (``(start, end, text)``, not overlapping) in a text of an object.

    The command holds the object's text as it will be, never the pattern; replaying a log needs no search."""
    obj = model.get_object(object_id)
    if source == DESCRIPTION:
        text = obj.body.description
        for start, end, new in sorted(edits, reverse=True):
            text = text[:start] + new + text[end:]
        return DescribeObject(object_id, text, False)
    if obj.body.paragraph is None:
        raise ValueError("an image carries no text")
    return SetParagraph(object_id, replace_spans(obj.body.paragraph, edits, author))


__all__ = ["BOX", "DESCRIPTION", "LABEL", "SOURCES", "ObjectText", "object_texts"]
