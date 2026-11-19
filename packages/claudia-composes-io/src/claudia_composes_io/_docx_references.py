"""References in a docx, both ways (step H; design in ``e9-composes-outline-references-toc.md``, 9).

**Writing.** A paragraph a reference points at gets a bookmark around its words (``_Ref`` and its id); a reference is
Word's field for it, ``REF`` (its number with ``\\r``, its words without) or ``PAGEREF`` for its page, with what it
reads as now as the field's result, so a program that does not update fields shows it too. A reference to anything
that is not a paragraph (a picture) cannot be a field: its name is written as words.

**Reading.** A ``REF`` or ``PAGEREF`` field whose bookmark starts a paragraph becomes a reference to that paragraph;
any other is read as the words of its result.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from claudia_core import FIELD_CHAR, RefField, Show, Shown

from ._references import ReadReference

_REF = re.compile(r"^\s*(REF|PAGEREF)\s+(\S+)(.*)$")
_BOOKMARK_CHARS = re.compile(r"[^A-Za-z0-9_]")


def bookmark_name(paragraph_id: str) -> str:
    """The bookmark a reference to this paragraph names: Word's ``_Ref`` and the id (letters, digits, ``_``)."""
    return f"_Ref_{_BOOKMARK_CHARS.sub('_', paragraph_id)}"[:40]


def mark_targets(paragraph: Any, name: str, ids: Iterator[int]) -> None:
    """Put a bookmark called ``name`` around the words of the python-docx ``paragraph``."""
    element = paragraph._p  # python-docx's documented way to reach markup it does not model
    number = str(next(ids))
    start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
    start.set(qn("w:id"), number)
    start.set(qn("w:name"), name)
    end.set(qn("w:id"), number)
    properties = element.find(qn("w:pPr"))
    if properties is not None:
        properties.addnext(start)
    else:
        element.insert(0, start)
    element.append(end)


def _run(child: Any = None, text: str | None = None) -> Any:
    run = OxmlElement("w:r")
    if child is not None:
        run.append(child)
    if text is not None:
        said = OxmlElement("w:t")
        said.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        said.text = text
        run.append(said)
    return run


def _char(kind: str) -> Any:
    char = OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), kind)
    return _run(char)


def _instruction(text: str) -> Any:
    said = OxmlElement("w:instrText")
    said.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    said.text = f" {text} "
    return _run(said)


def reference_runs(field: RefField, shown: Shown, targets: set[str]) -> list[Any]:
    """The runs a reference is written as: Word's field for it with what it reads as now, or (for a reference to
    something that is no paragraph) those words alone."""
    if field.target not in targets:
        return [_run(text=shown.text)]
    name = bookmark_name(field.target)
    if field.show == "page":
        instruction = f"PAGEREF {name} \\h"
    else:
        instruction = f"REF {name} {'\\r ' if field.show == 'number' else ''}\\h"
    return [_char("begin"), _instruction(instruction), _char("separate"), _run(text=shown.text), _char("end")]


def swap_fields(paragraph: Any, fields: list[list[Any]]) -> None:
    """Put the runs of each field in place of the U+FFFC it stands at in the written ``paragraph``, in order. A run is
    cut where a U+FFFC stands: its words before stay, the field's runs follow, then the rest of the run in its look."""
    queue = iter(fields)
    for said in list(paragraph._p.iter(qn("w:t"))):
        text = said.text or ""
        if FIELD_CHAR not in text:
            continue
        run = said.getparent()
        properties = run.find(qn("w:rPr"))
        following = list(said.itersiblings())
        pieces = text.split(FIELD_CHAR)
        said.text = pieces[0]
        if not pieces[0]:
            run.remove(said)
        at = run
        for n, piece in enumerate(pieces[1:], start=1):
            for made in next(queue, []):
                at.addnext(made)
                at = made
            rest = following if n == len(pieces) - 1 else []
            if piece or rest:
                tail = _run(text=piece) if piece else _run()
                tail.extend(rest)
                if properties is not None:
                    tail.insert(0, etree.fromstring(etree.tostring(properties)))
                at.addnext(tail)
                at = tail
        if all(child.tag == qn("w:rPr") for child in run):
            run.getparent().remove(run)


def bookmarks_starting(element: Any) -> list[str]:
    """The names of the bookmarks that start in a paragraph before any of its words."""
    found = []
    for child in element.iterchildren():
        if child.tag == qn("w:bookmarkStart"):
            found.append(child.get(qn("w:name")))
        elif child.tag == qn("w:r") and child.find(qn("w:t")) is not None:
            break
    return found


def bookmarks_around(element: Any) -> list[str]:
    """The names of the bookmarks that surround all the words of a paragraph: they start before its first word and end
    after its last, and a bookmark around a part of the words (or around more than the paragraph) is not among them."""
    around: dict[str, str] = {}  # ... that started before any word
    seen_words = False
    ended: list[str] = []
    for child in element.iterchildren():
        if child.tag == qn("w:bookmarkStart"):
            if not seen_words:
                around[child.get(qn("w:id"))] = child.get(qn("w:name"))
        elif child.tag == qn("w:bookmarkEnd"):
            if seen_words and child.get(qn("w:id")) in around:
                ended.append(child.get(qn("w:id")))
        elif any(True for _ in child.iter(qn("w:t"), qn("w:instrText"))):
            seen_words = True
            ended.clear()  # an end before this word did not come after the last one
    return [around[i] for i in around if i in ended]


def has_references(element: Any) -> bool:
    """Does the paragraph hold a ``REF`` or ``PAGEREF`` field?"""
    return any(_REF.match(said.text or "") for said in element.iter(qn("w:instrText")))


def _paragraph_of(node: Any) -> Any:
    """The paragraph a node of the body is words of: the nearest ``w:p`` around it."""
    found = node.getparent()
    while found is not None and found.tag != qn("w:p"):
        found = found.getparent()
    return found


def read_words(element: Any) -> tuple[str, list[ReadReference]]:
    """The words of a paragraph with a U+FFFC for each ``REF``/``PAGEREF`` field, and those fields, in order. Words of
    other fields are their results, as python-docx reads them."""
    text: list[str] = []
    found: list[ReadReference] = []
    state = "words"  # or "instruction", "result"
    instruction, result = "", list[str]()
    said = element.iter(qn("w:t"), qn("w:instrText"), qn("w:fldChar"), qn("w:tab"), qn("w:br"))
    # the words of a text box or a shape hanging in the paragraph are its own
    for node in (node for node in said if _paragraph_of(node) is element):
        if node.tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            if kind == "begin":
                state, instruction, result = "instruction", "", []
            elif kind == "separate":
                state = "result"
            elif kind == "end":
                matched = _REF.match(instruction)
                if matched:
                    text.append(FIELD_CHAR)
                    numbered = "\\r" in matched.group(3)
                    show: Show = "page" if matched.group(1) == "PAGEREF" else ("number" if numbered else "text")
                    found.append(ReadReference(matched.group(2), show, "".join(result)))
                else:
                    text.extend(result)
                state = "words"
        elif node.tag == qn("w:instrText"):
            if state == "instruction":
                instruction += node.text or ""
        elif node.tag in (qn("w:tab"), qn("w:br")):
            (result if state == "result" else text).append("\t" if node.tag == qn("w:tab") else "\n")
        elif state == "result":
            result.append(node.text or "")
        elif state == "words":
            text.append(node.text or "")
    return "".join(text), found


__all__ = [
    "bookmark_name",
    "bookmarks_starting",
    "has_references",
    "mark_targets",
    "read_words",
    "reference_runs",
    "swap_fields",
]
