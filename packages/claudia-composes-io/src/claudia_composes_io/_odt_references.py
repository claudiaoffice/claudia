"""References in an odt, both ways (step H; design in ``e9-composes-outline-references-toc.md``, 9).

**Writing.** A paragraph a reference points at starts with a ``text:bookmark`` (``ref-`` and its id); a reference is a
``text:bookmark-ref`` to it with the format of what it shows (``number``, ``text``, ``page``) and what it reads as now
as its content, so a program that does not update it shows that. A reference to anything that is not a paragraph (a
picture) is written as its words.

**Reading.** A ``text:bookmark-ref`` whose bookmark starts a paragraph becomes a reference to that paragraph; any other
is read as its words.
"""

from __future__ import annotations

import copy

from lxml import etree

from claudia_core import FIELD_CHAR, RefField, Show, Shown
from claudia_odf_io import NS, read_text

from ._references import ReadReference

_REFERENCE = f"{{{NS['text']}}}bookmark-ref"
_BOOKMARKS = {f"{{{NS['text']}}}bookmark", f"{{{NS['text']}}}bookmark-start"}
_BOOKMARKS_TAG = f"{{{NS['text']}}}bookmark"
_NAME = f"{{{NS['text']}}}name"
_ANNOTATION = f"{{{NS['office']}}}annotation"
_REF_NAME = f"{{{NS['text']}}}ref-name"
_FORMAT = f"{{{NS['text']}}}reference-format"
#: OpenDocument's reference format for what a reference shows (a name is words: there is no field for it).
_FORMATS: dict[str, str] = {"number": "number", "number-text": "text", "text": "text", "page": "page"}


def bookmark_name(paragraph_id: str) -> str:
    """The bookmark a reference to this paragraph names."""
    return f"ref-{paragraph_id}"


def mark_target(paragraph: etree._Element, name: str) -> None:
    """Start ``paragraph`` with a bookmark called ``name``."""
    bookmark = etree.Element(_BOOKMARKS_TAG)
    bookmark.set(_NAME, name)
    bookmark.tail, paragraph.text = paragraph.text, None
    paragraph.insert(0, bookmark)


def reference_item(field: RefField, shown: Shown, targets: set[str]) -> etree._Element | str:
    """What a reference is written as: a ``text:bookmark-ref`` reading as it does now, or its words alone."""
    if field.target not in targets or field.show not in _FORMATS:
        return shown.text
    element = etree.Element(_REFERENCE)
    element.set(_FORMAT, _FORMATS[field.show])
    element.set(_REF_NAME, bookmark_name(field.target))
    element.text = shown.text
    return element


def swap_fields(paragraph: etree._Element, items: list[etree._Element | str]) -> None:
    """Put each item in place of the U+FFFC it stands at in the written ``paragraph``, in order."""
    queue = iter(items)
    for holder in [paragraph, *paragraph.iterdescendants()]:
        for side in ("text", "tail"):
            if holder is paragraph and side == "tail":
                continue
            words = getattr(holder, side)
            if not words or FIELD_CHAR not in words:
                continue
            pieces = words.split(FIELD_CHAR)
            setattr(holder, side, pieces[0])
            parent, after = (holder, None) if side == "text" else (_parent(holder), holder)
            for piece in pieces[1:]:
                item = next(queue, "")
                if isinstance(item, str):
                    _add_words(parent, after, item + piece)
                    continue
                item.tail = piece
                if after is None:
                    parent.insert(0, item)
                else:
                    after.addnext(item)
                after = item


def _parent(element: etree._Element) -> etree._Element:
    parent = element.getparent()
    if parent is None:
        raise ValueError("an element of a paragraph has a parent")
    return parent


def _add_words(parent: etree._Element, after: etree._Element | None, words: str) -> None:
    if after is None:
        parent.text = (parent.text or "") + words
    else:
        after.tail = (after.tail or "") + words


def bookmarks_starting(paragraph: etree._Element) -> list[str]:
    """The names of the bookmarks a paragraph starts with, before any of its words."""
    if (paragraph.text or "").strip():
        return []
    found = []
    for child in paragraph:
        if child.tag == _ANNOTATION:  # a comment around the words is not a word
            if (child.tail or "").strip():
                break
            continue
        if child.tag not in _BOOKMARKS:
            break
        found.append(child.get(_NAME, ""))
        if (child.tail or "").strip():
            break
    return found


def read_words(paragraph: etree._Element) -> tuple[str, list[ReadReference]]:
    """The words of a paragraph with a U+FFFC for each ``text:bookmark-ref``, and those references, in order."""
    references = list(paragraph.iter(_REFERENCE))
    if not references:
        return read_text(paragraph), []
    found = []
    flat = copy.deepcopy(paragraph)
    for element in list(flat.iter(_REFERENCE)):
        fmt = element.get(_FORMAT, "text")
        show: Show = "page" if fmt == "page" else ("number" if fmt.startswith("number") else "text")
        words = "".join(str(piece) for piece in element.itertext())
        found.append(ReadReference(element.get(_REF_NAME, ""), show, words))
        parent, before = _parent(element), element.getprevious()
        _add_words(parent, before, FIELD_CHAR + (element.tail or ""))
        parent.remove(element)
    return read_text(flat), found
