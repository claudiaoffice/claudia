"""A table of contents in a docx, both ways (E9.31, step E).

**Writing.** A table of contents is what Word writes for one: a content control (``w:sdt``, gallery "Table of
Contents") holding a ``TOC`` field (``TOC \\o "1-3" \\h \\z \\u``) whose result is the entries, one paragraph each in
Word's styles ``toc 1`` … ``toc 9``, **without page numbers**: pages are the layout's, and a docx is laid out by Word.
The document asks Word to update its fields when it is opened (``w:updateFields``), so the pages appear there.

**Reading.** A ``TOC`` field, in a content control or on its own, becomes one generated paragraph with the levels of
its ``\\o`` switch; the entries Word wrote are not read (they are derived again from the headings). The model's
"Contents" paragraph is written outside the content control, in Word's style "TOC Heading", and read back as one.
"""

from __future__ import annotations

import re
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from claudia_core import ContentsEntry, Toc

#: Word's instruction for a table of contents of these levels, with hyperlinks, without page numbers in web views
#: and using the outline levels.
_INSTRUCTION = 'TOC \\o "{first}-{last}" \\h \\z \\u'
_LEVELS = re.compile(r'\\o\s+"(\d)-(\d)"')
_GALLERY = "Table of Contents"


def _field_char(kind: str) -> Any:
    run = OxmlElement("w:r")
    char = OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), kind)
    run.append(char)
    return run


def _instruction(text: str) -> Any:
    run = OxmlElement("w:r")
    said = OxmlElement("w:instrText")
    said.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    said.text = f" {text} "
    run.append(said)
    return run


def _paragraph(style_id: str | None, text: str = "", before: tuple = (), after: tuple = ()) -> Any:
    """A ``w:p`` in a style, with ``text``, the runs ``before`` it and those ``after`` it (the field's marks)."""
    paragraph = OxmlElement("w:p")
    if style_id:
        properties = OxmlElement("w:pPr")
        style = OxmlElement("w:pStyle")
        style.set(qn("w:val"), style_id)
        properties.append(style)
        paragraph.append(properties)
    paragraph.extend(before)
    if text:
        run = OxmlElement("w:r")
        said = OxmlElement("w:t")
        said.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        said.text = text
        run.append(said)
        paragraph.append(run)
    paragraph.extend(after)
    return paragraph


def write_contents(document: Any, paragraph: Any, toc: Toc, entries: tuple[ContentsEntry, ...], style_of: Any) -> None:
    """Make the (empty) python-docx ``paragraph`` the table of contents ``toc``: it is replaced by a content
    control holding the ``TOC`` field and its ``entries`` without page numbers. ``style_of(style_id)`` gives the Word
    style id of an entry's style (``None`` for the default)."""
    control = OxmlElement("w:sdt")
    properties = OxmlElement("w:sdtPr")
    part = OxmlElement("w:docPartObj")
    gallery = OxmlElement("w:docPartGallery")
    gallery.set(qn("w:val"), _GALLERY)
    unique = OxmlElement("w:docPartUnique")
    part.extend([gallery, unique])
    properties.append(part)
    content = OxmlElement("w:sdtContent")
    control.extend([properties, content])
    said = [(style_of(entry.style), _words(entry, toc)) for entry in entries] or [(None, "")]
    instruction = _instruction(_INSTRUCTION.format(first=toc.first, last=toc.last))
    opening = (_field_char("begin"), instruction, _field_char("separate"))
    last = len(said) - 1
    content.extend(
        _paragraph(style, words, opening if n == 0 else (), (_field_char("end"),) if n == last else ())
        for n, (style, words) in enumerate(said)
    )
    paragraph._p.addprevious(control)
    paragraph._p.getparent().remove(paragraph._p)
    ask_word_to_update(document)


def _words(entry: ContentsEntry, toc: Toc) -> str:
    return f"{entry.number}\t{entry.text}" if toc.numbers and entry.number else entry.text


def ask_word_to_update(document: Any) -> None:
    """``w:updateFields`` in the settings: Word offers to update the fields (the pages of the contents) on opening."""
    settings = document.settings.element
    if settings.find(qn("w:updateFields")) is not None:
        return
    flag = OxmlElement("w:updateFields")
    flag.set(qn("w:val"), "true")
    # w:updateFields comes early in w:settings: before everything but the view, zoom and protection settings
    earlier = ("w:writeProtection", "w:view", "w:zoom", "w:removePersonalInformation", "w:removeDateAndTime")
    before = [c for c in settings if etree.QName(c).localname in {e[2:] for e in earlier}]
    if before:
        before[-1].addnext(flag)
    else:
        settings.insert(0, flag)


def contents_in(element: etree._Element) -> Toc | None:
    """The table of contents a body element of a docx is (a content control or a paragraph holding a ``TOC``
    field), or ``None``."""
    for said in element.iter(qn("w:instrText")):
        text = (said.text or "").strip()
        if text.startswith("TOC"):
            found = _LEVELS.search(text)
            first, last = (int(found.group(1)), int(found.group(2))) if found else (1, 3)
            first, last = max(1, min(first, 9)), max(1, min(last, 9))
            return Toc(min(first, last), max(first, last))
    return None


def body_order(document: Any) -> list[tuple[int | None, Toc | None]]:
    """The body of a docx in order: ``(n, None)`` for the n-th of python-docx's ``document.paragraphs``, and
    ``(None, toc)`` for a table of contents (a content control holding a ``TOC`` field, or a field that runs over
    paragraphs of the body, whose paragraphs are its entries and are skipped). A Word "TOC Heading" inside the
    content control is not read: the model's own title paragraph is written outside it."""
    paragraphs = {p._p: n for n, p in enumerate(document.paragraphs)}  # noqa: SLF001
    order: list[tuple[int | None, Toc | None]] = []
    inside = False
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:sdt"):
            toc = contents_in(child)
            if toc is not None:
                order.append((None, toc))
            continue
        if child.tag != qn("w:p"):
            continue
        if inside:
            inside = not _ends(child)
            continue
        toc = contents_in(child)
        if toc is not None:
            order.append((None, toc))
            inside = not _ends(child)
            continue
        order.append((paragraphs[child], None))
    return order


def _ends(paragraph: etree._Element) -> bool:
    return any(c.get(qn("w:fldCharType")) == "end" for c in paragraph.iter(qn("w:fldChar")))
