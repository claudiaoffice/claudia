"""Names and descriptions in an odt (E1.13, D1311, D1318, A5/A6): a name a person gave is a bookmark around the words
of the paragraph; a description is an annotation (a review comment) around them, by the person exporting and dated the
day of the export. Reading, a bookmark around exactly the words of one paragraph is its name."""

from __future__ import annotations

from lxml import etree

from claudia_odf_io import NS

from ._annotations import Annotations

_Q = {
    name: f"{{{NS[prefix]}}}{local}"
    for name, (prefix, local) in {
        "start": ("text", "bookmark-start"),
        "end": ("text", "bookmark-end"),
        "point": ("text", "bookmark"),
        "name": ("text", "name"),
        "note": ("office", "annotation"),
        "note-end": ("office", "annotation-end"),
        "note-name": ("office", "name"),
        "creator": ("dc", "creator"),
        "date": ("dc", "date"),
        "p": ("text", "p"),
        "space": ("text", "s"),
        "tab": ("text", "tab"),
        "break": ("text", "line-break"),
    }.items()
}
_NO_WORDS = {_Q["start"], _Q["end"], _Q["point"], _Q["note"], _Q["note-end"], _Q["space"], _Q["tab"], _Q["break"]}


def _wrap(paragraph: etree._Element, start: etree._Element, end: etree._Element) -> None:
    """Put ``start`` before everything in ``paragraph`` and ``end`` after it."""
    start.tail, paragraph.text = paragraph.text, None
    paragraph.insert(0, start)
    paragraph.append(end)


def mark_name(paragraph: etree._Element, name: str) -> None:
    """Put a bookmark called ``name`` around the words of ``paragraph``."""
    start, end = etree.Element(_Q["start"]), etree.Element(_Q["end"])
    start.set(_Q["name"], name)
    end.set(_Q["name"], name)
    _wrap(paragraph, start, end)


def write_annotation(paragraph: etree._Element, number: int, text: str, notes: Annotations) -> None:
    """Put a comment ``text`` by ``notes.author`` at ``notes.when`` around the words of ``paragraph``."""
    label = f"claudia-comment-{number}"
    start, end = etree.Element(_Q["note"]), etree.Element(_Q["note-end"])
    start.set(_Q["note-name"], label)
    end.set(_Q["note-name"], label)
    if notes.author:
        etree.SubElement(start, _Q["creator"]).text = notes.author
    if notes.when:
        etree.SubElement(start, _Q["date"]).text = notes.when
    etree.SubElement(start, _Q["p"]).text = text
    _wrap(paragraph, start, end)


def annotate(paragraph: etree._Element, number: int, block_id: str, notes: Annotations) -> None:
    """Write what ``notes`` says about the paragraph ``block_id``, the ``number``-th of the text: the comment first, so
    that the name's bookmark is the outermost."""
    if comment := notes.comments.get(block_id):
        write_annotation(paragraph, number, comment, notes)
    if name := notes.names.get(block_id):
        mark_name(paragraph, name)


def bookmarks_around(paragraph: etree._Element) -> list[str]:
    """The names of the bookmarks that surround all the words of ``paragraph``: they start before its first word and
    end after its last. A point bookmark, one around a part of the words and one around more are not among them."""
    open_: set[str] = set()
    ended: set[str] = set()
    seen_words = bool((paragraph.text or "").strip())
    for child in paragraph:
        name = child.get(_Q["name"], "")
        if child.tag == _Q["start"] and not seen_words:
            open_.add(name)
        elif child.tag == _Q["end"] and seen_words and name in open_:
            ended.add(name)
        elif child.tag not in _NO_WORDS and "".join(map(str, child.itertext())).strip():
            seen_words = True
            ended.clear()
        if (child.tail or "").strip():
            seen_words = True
            ended.clear()
    return [name for name in dict.fromkeys(_names_in_order(paragraph)) if name in ended]


def _names_in_order(paragraph: etree._Element) -> list[str]:
    return [child.get(_Q["name"], "") for child in paragraph if child.tag == _Q["start"]]
