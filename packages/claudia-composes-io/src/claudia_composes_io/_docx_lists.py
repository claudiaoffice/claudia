"""Lists in a docx: reading ``w:numPr`` as items of lists, writing items with a ``w:num`` of their own list, and the
``w:abstractNum`` that says how each level is drawn (D453).

What the model has is explicit: a :class:`~claudia_core.ListDef` (scheme, start, name) and paragraphs that are items of
it at a level. What a docx has is a numbering part: a paragraph says ``w:numId`` and ``w:ilvl``, a ``w:num`` names a
``w:abstractNum``, and that has a ``w:lvl`` for each level. The two meet like this:

* A ``w:num`` is one list of the model: paragraphs with the same ``w:numId`` are items of it in document order,
  whatever lies between them, which is what Word counts too. A paragraph takes its numbering from its own ``w:numPr``
  or, where that lacks it, from its style (and the styles that one is based on); ``w:numId`` 0 means no list.
* The scheme of a list is the scheme of the document that draws its levels as the file does; a look no scheme has
  becomes a scheme of its own (E9.22, :mod:`claudia_composes_io._list_looks`). A level the model cannot say (another
  separator than a full stop, an ordinal, a picture bullet) leaves the list with the built-in scheme of its kind,
  and it is reported as ``list-look``: the model shows its own markers, and the file keeps its own.
* A heading style that Word numbers (a ``w:numPr`` in the style, at the level below its outline level) is numbered
  in that list in the model too (:attr:`claudia_core.StyleDef.numbering`): its paragraphs are no items of their own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.oxml import OxmlElement
from docx.oxml.ns import nsmap, qn
from docx.parts.numbering import NumberingPart
from lxml import etree

from claudia_core import MAX_LIST_LEVEL, LevelFormat, ListBook, ListDef, ListItem, Scheme, SchemeBook

from ._list_looks import read_word_level, scheme_for, word_level

#: How far each level moves the text in: a scheme says it in em, a docx wants twentieths of a point (0.4 cm per em).
_TWIPS_PER_EM = 227
_VAL = qn("w:val")


def _val(parent: etree._Element | None, tag: str) -> str | None:
    child = parent.find(qn(tag)) if parent is not None else None
    return child.get(_VAL) if child is not None else None


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None


# -- the look of a list ---------------------------------------------------------------------------------------------
def abstract_num(definition: ListDef, scheme: Scheme, abstract_id: int) -> etree._Element:
    """The ``w:abstractNum`` that makes a list of the model look as its ``scheme`` draws it: nine levels, each with
    its marker and its indent."""
    step = round(scheme.indent * _TWIPS_PER_EM)
    element = OxmlElement("w:abstractNum")
    element.set(qn("w:abstractNumId"), str(abstract_id))
    kind = OxmlElement("w:multiLevelType")
    kind.set(_VAL, "hybridMultilevel")
    element.append(kind)
    if definition.name:
        name = OxmlElement("w:name")
        name.set(_VAL, definition.name)
        element.append(name)
    for level in range(MAX_LIST_LEVEL + 1):
        marker = OxmlElement("w:lvl")
        marker.set(qn("w:ilvl"), str(level))
        start = OxmlElement("w:start")
        start.set(_VAL, str(definition.start if level == 0 and scheme.counts else 1))
        marker.append(start)
        number_format, text = OxmlElement("w:numFmt"), OxmlElement("w:lvlText")
        said = word_level(scheme.level(level), level)
        number_format.set(_VAL, said[0])
        text.set(_VAL, said[1])
        marker.extend([number_format, text])
        justify = OxmlElement("w:lvlJc")
        justify.set(_VAL, "left")
        marker.append(justify)
        properties, indent = OxmlElement("w:pPr"), OxmlElement("w:ind")
        indent.set(qn("w:left"), str(step * (level + 1)))
        indent.set(qn("w:hanging"), str(step))
        properties.append(indent)
        marker.append(properties)
        element.append(marker)
    return element


# -- the numbering part ---------------------------------------------------------------------------------------------
class Numbering:
    """The ``w:numbering`` element of a file, to look lists up in and to add lists to."""

    def __init__(self, root: etree._Element) -> None:
        self.root = root

    def _numbered(self, tag: str, attribute: str) -> dict[int, etree._Element]:
        found: dict[int, etree._Element] = {}
        for element in self.root.findall(qn(tag)):
            if (number := _int(element.get(qn(attribute)))) is not None:
                found.setdefault(number, element)
        return found

    def abstracts(self) -> dict[int, etree._Element]:
        return self._numbered("w:abstractNum", "w:abstractNumId")

    def nums(self) -> dict[int, etree._Element]:
        return self._numbered("w:num", "w:numId")

    def abstract_of(self, num: etree._Element) -> etree._Element | None:
        return self.abstracts().get(_int(_val(num, "w:abstractNumId")) or -1)

    def _next(self, existing: Iterable[int]) -> int:
        return max(existing, default=0) + 1

    def _add_abstract(self, definition: ListDef, scheme: Scheme) -> int:
        """Put the ``w:abstractNum`` of ``definition`` before the first ``w:num`` (the schema wants it there)."""
        abstract_id = self._next(self.abstracts())
        element = abstract_num(definition, scheme, abstract_id)
        first_num = self.root.find(qn("w:num"))
        if first_num is not None:
            first_num.addprevious(element)
        else:
            self.root.append(element)
        return abstract_id

    def add_list(self, definition: ListDef, scheme: Scheme) -> int:
        """The ``w:numId`` of a new list that looks as ``definition`` and its ``scheme`` say."""
        abstract_id = self._add_abstract(definition, scheme)
        num_id = self._next(self.nums())
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        target = OxmlElement("w:abstractNumId")
        target.set(_VAL, str(abstract_id))
        num.append(target)
        last = self.root.findall(qn("w:num"))
        if last:
            last[-1].addnext(num)
        else:
            self.root.append(num)
        return num_id

    def restyle(self, num_id: int, definition: ListDef, scheme: Scheme) -> None:
        """Make the list ``num_id`` look as ``definition`` and its ``scheme`` say, so that every paragraph follows."""
        num = self.nums()[num_id]
        target = num.find(qn("w:abstractNumId"))
        assert target is not None  # a w:num always names its abstractNum (schema)
        target.set(_VAL, str(self._add_abstract(definition, scheme)))
        for override in num.findall(qn("w:lvlOverride")):
            num.remove(override)


# -- reading ---------------------------------------------------------------------------------------------------------
@dataclass
class ListReading:
    """What the paragraphs of a docx say about lists."""

    book: ListBook = field(default_factory=ListBook)
    #: The schemes the lists are drawn with: the built-in ones and those the file's lists need.
    schemes: SchemeBook = field(default_factory=SchemeBook)
    #: The item each paragraph is (the paragraphs that are no item are not in it).
    items: dict[etree._Element, ListItem] = field(default_factory=dict)
    #: The items that a paragraph has only from its style (Word numbers a heading style that way).
    styled: set[etree._Element] = field(default_factory=set)
    #: The ``w:numId`` of each list of the book.
    num_of: dict[str, int] = field(default_factory=dict)
    #: Lists whose look the model does not show, and levels deeper than the model has.
    odd_looks: int = 0
    too_deep: int = 0


def numbering_of_style(style: object | None) -> tuple[int | None, int | None]:
    """The ``w:numId`` and ``w:ilvl`` a paragraph style gives (through the styles it is based on), where it says."""
    num_id = level = None
    seen = 0
    while style is not None and seen < 20:  # a cycle of base styles must not hang the reading
        properties = style.element.pPr  # type: ignore[attr-defined]
        numbering = properties.find(qn("w:numPr")) if properties is not None else None
        if numbering is not None:
            num_id = _int(_val(numbering, "w:numId")) if num_id is None else num_id
            level = _int(_val(numbering, "w:ilvl")) if level is None else level
        style = style.base_style  # type: ignore[attr-defined]
        seen += 1
    return num_id, level


def numbering_of(paragraph: object) -> tuple[int | None, int | None, bool]:
    """The ``w:numId`` and ``w:ilvl`` of a python-docx paragraph: its own, and its style's where it has none; and
    whether the list comes from the style."""
    properties = paragraph._p.pPr  # type: ignore[attr-defined]
    own = properties.find(qn("w:numPr")) if properties is not None else None
    num_id, level = _int(_val(own, "w:numId")), _int(_val(own, "w:ilvl"))
    styled = num_id is None
    if num_id is None or level is None:
        from_style = numbering_of_style(paragraph.style)  # type: ignore[attr-defined]
        num_id = from_style[0] if num_id is None else num_id
        level = from_style[1] if level is None else level
    return num_id, level, styled


def read_lists(paragraphs: Iterable[object], numbering: Numbering | None) -> ListReading:
    """The lists of a text and the items among its ``paragraphs`` (python-docx paragraphs, in document order), with
    the lists looked up in ``numbering`` (``None`` for a file that has no numbering part)."""
    reading = ListReading()
    if numbering is None:
        return reading
    nums, list_of = numbering.nums(), {}
    for paragraph in paragraphs:
        num_id, level, styled = numbering_of(paragraph)
        if not num_id or num_id not in nums:
            continue  # no numbering, "numId 0" (Word's way of saying none), or a list the file does not define
        if num_id not in list_of:
            list_of[num_id] = _definition(nums[num_id], numbering, reading)
        if (level or 0) > MAX_LIST_LEVEL:
            reading.too_deep += 1
        reading.items[paragraph._p] = ListItem(list_of[num_id], min(max(level or 0, 0), MAX_LIST_LEVEL))  # type: ignore[attr-defined]
        if styled:
            reading.styled.add(paragraph._p)  # type: ignore[attr-defined]
        reading.num_of[list_of[num_id]] = num_id
    return reading


def _definition(num: etree._Element, numbering: Numbering, reading: ListReading) -> str:
    """Add the list ``num`` to the book of ``reading``; its id."""
    abstract = numbering.abstract_of(num)
    first = (
        next((e for e in abstract.findall(qn("w:lvl")) if _int(e.get(qn("w:ilvl"))) == 0), None)
        if abstract is not None
        else None
    )
    counts = first is not None and _val(first, "w:numFmt") not in ("bullet", "none", None)
    start = 1
    if counts:
        start = _int(_val(first, "w:start")) or 1
        for override in num.findall(qn("w:lvlOverride")):
            if _int(override.get(qn("w:ilvl"))) == 0 and (changed := _int(_val(override, "w:startOverride"))):
                start = changed
    called = _val(abstract, "w:name") if abstract is not None else None
    name = called if called and called.strip() and len(called) <= 60 and called.isprintable() else None
    scheme = None if abstract is None else scheme_for(_levels(abstract), counts, name, reading.schemes)
    if scheme is None:
        reading.odd_looks += 1
        scheme = "numbers" if counts else "bullets"
    list_id = reading.book.unique_id()
    reading.book.add(ListDef(list_id, scheme, max(1, min(start, 999_999)), name))
    return list_id


def _levels(abstract: etree._Element) -> dict[int, LevelFormat | None]:
    """What each level of a ``w:abstractNum`` draws, as a level of a scheme (``None`` where none can say it)."""
    found: dict[int, LevelFormat | None] = {}
    for level in abstract.findall(qn("w:lvl")):
        number = _int(level.get(qn("w:ilvl")))
        if number is not None and 0 <= number <= MAX_LIST_LEVEL:
            found[number] = read_word_level(_val(level, "w:numFmt"), _val(level, "w:lvlText"), number)
    return found


# -- writing ---------------------------------------------------------------------------------------------------------
def numbering_in(document: object, *, create: bool = False) -> Numbering | None:
    """The numbering of a python-docx ``document``. A file that has none gets one only when ``create``: python-docx's
    own ``numbering_part`` makes it, which a file that needs no list should not be given."""
    part = document.part  # type: ignore[attr-defined]
    try:
        return Numbering(part.part_related_by(RT.NUMBERING).element)
    except KeyError:
        if not create:
            return None
    # python-docx has no way to make a numbering part (its own ``numbering_part`` raises where there is none)
    blob = f'<w:numbering xmlns:w="{nsmap["w"]}"/>'.encode()
    made = NumberingPart.load(PackURI("/word/numbering.xml"), CT.WML_NUMBERING, blob, part.package)
    part.relate_to(made, RT.NUMBERING)
    return Numbering(made.element)


class ListWriter:
    """Writes items into the paragraphs of a document: one ``w:num`` for each list of ``book``, made when a first item
    needs it. ``known`` are the lists the file already has (a list id and the ``w:numId`` it is)."""

    def __init__(
        self, document: object, book: ListBook, schemes: SchemeBook, known: dict[str, int] | None = None
    ) -> None:
        self.document = document
        self.book = book
        self.schemes = schemes
        self.num_of = dict(known or {})
        self._owned: set[str] = set()  # the parts of the package that the writing changed

    def owned(self) -> set[str]:
        """The parts of the package this writer changed (besides the text): the numbering, and where it is new, what
        says that the package has it."""
        return set(self._owned)

    def _touch(self, *, created: bool) -> None:
        self._owned.add(str(self.document.part.numbering_part.partname).lstrip("/"))  # type: ignore[attr-defined]
        if created:
            self._owned |= {"[Content_Types].xml", "word/_rels/document.xml.rels"}

    def num_id(self, list_id: str) -> int:
        if list_id not in self.num_of:
            created = numbering_in(self.document) is None
            numbering = numbering_in(self.document, create=True)
            assert numbering is not None  # create=True always has one
            definition = self.book.get(list_id)
            self.num_of[list_id] = numbering.add_list(definition, self._scheme(definition))
            self._touch(created=created)
        return self.num_of[list_id]

    def restyle(self, list_id: str) -> None:
        """The list the file has as ``list_id`` is drawn as the book now says."""
        numbering = numbering_in(self.document)
        if numbering is not None and list_id in self.num_of and self.num_of[list_id] in numbering.nums():
            definition = self.book.get(list_id)
            numbering.restyle(self.num_of[list_id], definition, self._scheme(definition))
            self._touch(created=False)
        else:
            self.num_of.pop(list_id, None)  # the file lost it: the next item makes it

    def _scheme(self, definition: ListDef) -> Scheme:
        """The scheme a list is drawn with; one the document lost is drawn as plain numbers or bullets."""
        if definition.scheme in self.schemes:
            return self.schemes.get(definition.scheme)
        return next(s for s in SchemeBook() if s.id == "numbers")

    def write(self, paragraph: object, item: ListItem | None) -> None:
        """Make ``paragraph`` (a python-docx paragraph) an item as ``item`` says, or no item for ``None``."""
        element = paragraph._p  # type: ignore[attr-defined]
        if item is None:
            if element.pPr is not None:
                element.pPr._remove_numPr()
            if numbering_of_style(paragraph.style)[0]:  # type: ignore[attr-defined]
                element.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 0  # its style would list it
            return
        properties = element.get_or_add_pPr()
        properties._remove_numPr()
        numbering = properties.get_or_add_numPr()
        numbering.get_or_add_ilvl().val = item.level
        numbering.get_or_add_numId().val = self.num_id(item.list)
