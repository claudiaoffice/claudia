"""References read from a file, the same for docx and odt (step H): a field that names a bookmark at the start of a
paragraph becomes a reference to that paragraph; one that names anything else is read as the words it showed."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from claudia_composes import Paragraph, Run
from claudia_core import FIELD_CHAR, RefField, Show, plain


@dataclass(frozen=True)
class ReadReference:
    """A reference as read: the bookmark it names, what it shows and the words the file last showed for it."""

    bookmark: str
    show: Show
    words: str


def with_references(paragraph: Paragraph, found: Sequence[ReadReference], marked: Mapping[str, str]) -> Paragraph:
    """``paragraph``, whose text has a U+FFFC for each of ``found``, with those references made fields of it, or their
    words where their bookmark starts no paragraph (``marked``: the paragraph each bookmark starts, by name)."""
    pieces = paragraph.text.split(FIELD_CHAR)
    text, fields = pieces[0], []
    for reference, piece in zip(found, pieces[1:], strict=True):
        target = marked.get(reference.bookmark)
        if target is not None:
            text += FIELD_CHAR
            fields.append(RefField(target, reference.show))
        else:
            text += plain(reference.words)
        text += piece
    return replace(paragraph, text=text, runs=(Run(len(text), None),) if text else (), fields=tuple(fields))
