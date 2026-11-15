"""Paragraphs added to and removed from a kept docx: where a new paragraph goes, and what a removed one takes with it
(D456)."""

from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn

#: What a paragraph can hold that its text does not show, by the name it is reported with when the paragraph goes.
_HIDDEN = (
    ("frame", ("w:drawing", "w:pict", "w:object")),
    ("footnote", ("w:footnoteReference",)),
    ("endnote", ("w:endnoteReference",)),
    ("comment", ("w:commentReference",)),
    ("link", ("w:hyperlink",)),
    ("tracked-change", ("w:ins", "w:del")),
)


def hidden_content(paragraph: Any) -> list[str]:
    """What ``paragraph`` (a ``w:p``) shows that its text cannot -- ``"frame"``, ``"footnote"``, ``"endnote"``,
    ``"comment"``, ``"link"`` or ``"tracked-change"``, one entry for each, kind by kind."""
    found: list[str] = []
    for kind, tags in _HIDDEN:
        found += [kind for tag in tags for _ in paragraph.iter(qn(tag))]
    return found


def ends_a_section(paragraph: Any) -> bool:
    """Whether ``paragraph`` carries the properties of the section before it: taking it out would join two sections."""
    properties = paragraph.find(qn("w:pPr"))
    return properties is not None and properties.find(qn("w:sectPr")) is not None


def remove(paragraph: Any) -> None:
    """Take ``paragraph`` out of the document -- or, when it ends a section, only what it says, so that the section
    stays as it is."""
    if not ends_a_section(paragraph):
        parent = paragraph.getparent()
        assert parent is not None  # a paragraph of a document has the body (or a cell) for its parent
        parent.remove(paragraph)
        return
    for child in list(paragraph):
        if child.tag != qn("w:pPr"):
            paragraph.remove(child)


def place(new: Any, after: Any | None, before: Any | None) -> None:
    """Put the new paragraph ``new`` (which a document has put last) right after the element ``after`` -- the paragraph
    that comes before it in the text -- or else right before ``before``, the one that comes after it. With neither the
    text has no other paragraph in the file, and it stays where it is."""
    if after is not None:
        after.addnext(new)
    elif before is not None:
        before.addprevious(new)
