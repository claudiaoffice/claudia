"""Lists in an odt: reading them as items of lists, writing items as ``text:list``, and the list styles that say how
each level is drawn (D453).

What the model has is explicit: a :class:`~claudia_core.ListDef` (scheme, start, name) and paragraphs that are items of
it at a level. What an odt has is a tree: a ``text:list`` holds ``text:list-item`` elements, each with its paragraph
and, for the next level, another ``text:list``. A ``text:list-style`` (named by the list's ``text:style-name``) says
what each level shows. The two meet like this:

* A top-level ``text:list`` is one list of the model; one that continues another (``text:continue-list``, or
  ``text:continue-numbering`` after a list of the same style) is the same list, so numbering goes on, as it does in
  the model for items that share a list id.
* The first paragraph of a ``text:list-item`` is an item at the depth of its ``text:list``. Any further paragraph in
  the same item is a paragraph of the text like any other (Word and LibreOffice call it "unnumbered").
* The scheme of a list is the scheme of the document that draws the levels of its style as the file does; a look no
  scheme has becomes a scheme of its own (E9.22, :mod:`claudia_composes_io._list_looks`). A level the model cannot say
  (a picture bullet, a number format it does not know) leaves the list with the built-in scheme of its kind, and it is
  reported as ``list-look``: the model shows its own markers, and the file keeps its own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from lxml import etree

from claudia_core import MAX_LIST_LEVEL, ListBook, ListDef, ListItem, Scheme, SchemeBook, StyleBook
from claudia_odf_io import LEVEL_BULLET, LEVEL_NUMBER, NS, OUTLINE_LEVEL, level_style, list_style, read_levels

from ._list_looks import scheme_for

_XML_ID = f"{{{NS['xml']}}}id"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


P, H = _q("text", "p"), _q("text", "h")
LIST, LIST_ITEM = _q("text", "list"), _q("text", "list-item")
LIST_HEADER, NUMBERED = _q("text", "list-header"), _q("text", "numbered-paragraph")
#: What holds paragraphs and is part of a list, not a thing of its own.
LIST_PARTS = {LIST, LIST_ITEM, LIST_HEADER, NUMBERED}
_STYLE_NAME, _CONTINUE_LIST = _q("text", "style-name"), _q("text", "continue-list")
_CONTINUE_NUMBERING = _q("text", "continue-numbering")
_LEVEL_STYLES = (LEVEL_NUMBER, LEVEL_BULLET)


# -- the style of a list --------------------------------------------------------------------------------------------
def _style_elements(roots: Iterable[etree._Element]) -> dict[str, etree._Element]:
    """Every ``text:list-style`` of the file by name."""
    found: dict[str, etree._Element] = {}
    for root in roots:
        for style in root.iter(_q("text", "list-style")):
            if name := style.get(_q("style", "name")):
                found.setdefault(name, style)
    return found


def _first_level(style: etree._Element | None) -> etree._Element | None:
    if style is None:
        return None
    return next((e for e in style if e.tag in _LEVEL_STYLES and e.get(_q("text", "level")) == "1"), None)


def _positive(text: str | None) -> int | None:
    try:
        return int(text) if text and int(text) >= 1 else None
    except ValueError:
        return None


# -- reading ---------------------------------------------------------------------------------------------------------
@dataclass
class ListReading:
    """What the paragraphs of a text say about lists."""

    book: ListBook = field(default_factory=ListBook)
    #: The schemes the lists are drawn with: the built-in ones and those the file's lists need.
    schemes: SchemeBook = field(default_factory=SchemeBook)
    #: The item each paragraph is (the paragraphs that are no item are not in it).
    items: dict[etree._Element, ListItem] = field(default_factory=dict)
    #: The top-level element each paragraph is in (the paragraph itself when it is in no list).
    container: dict[etree._Element, etree._Element] = field(default_factory=dict)
    #: The list a top-level ``text:list`` is of, and the name of its list style.
    list_of: dict[etree._Element, str] = field(default_factory=dict)
    style_of: dict[str, str | None] = field(default_factory=dict)
    #: Lists whose look the model does not show, and levels deeper than the model has.
    odd_looks: int = 0
    too_deep: int = 0


def top_of(paragraph: etree._Element) -> etree._Element:
    """The outermost element of the list ``paragraph`` is in, or the paragraph itself."""
    found = paragraph
    while (parent := found.getparent()) is not None and parent.tag in LIST_PARTS:
        found = parent
    return found


def _identity(top: etree._Element, reading: ListReading, by_id: dict[str, str], last_of_style: dict) -> str:
    """The id of the list a top-level list element is of: that of the list it continues, or a new one."""
    follows = top.get(_CONTINUE_LIST)
    if follows and follows in by_id:
        return by_id[follows]
    name = top.get(_STYLE_NAME)
    if top.get(_CONTINUE_NUMBERING) == "true" and name in last_of_style:
        return last_of_style[name]
    return reading.book.unique_id()


def _definition(list_id: str, top: etree._Element, styles: dict[str, etree._Element], reading: ListReading) -> ListDef:
    style = styles.get(top.get(_STYLE_NAME) or "")
    level = _first_level(style)
    counts = level is not None and level.tag == _q("text", "list-level-style-number")
    start = 1
    if counts:
        start = _positive(level.get(_q("text", "start-value")) if level is not None else None) or 1
        item = top.find(LIST_ITEM)
        start = _positive(item.get(_q("text", "start-value")) if item is not None else None) or start
    display = style.get(_q("style", "display-name")) if style is not None else None
    name = display if display and display.strip() and len(display) <= 60 and display.isprintable() else None
    levels = None if style is None else read_levels(style, _LEVEL_STYLES)
    scheme = None if levels is None else scheme_for(levels, counts, name, reading.schemes)
    if scheme is None:
        reading.odd_looks += 1
        scheme = "numbers" if counts else "bullets"
    return ListDef(list_id, scheme, min(start, 999_999), name)


def read_lists(paragraphs: Iterable[etree._Element], roots: Iterable[etree._Element]) -> ListReading:
    """The lists of a text and the items among its ``paragraphs`` (in document order), with the styles of lists
    looked up in ``roots`` (the content and the styles of the file)."""
    styles = _style_elements(roots)
    reading = ListReading()
    by_id: dict[str, str] = {}
    last_of_style: dict[str | None, str] = {}
    for paragraph in paragraphs:
        top = top_of(paragraph)
        reading.container[paragraph] = top
        if top.tag not in (LIST, NUMBERED):
            continue
        if top not in reading.list_of:
            list_id = _identity(top, reading, by_id, last_of_style)
            reading.list_of[top] = list_id
            if list_id not in reading.book:
                reading.book.add(_definition(list_id, top, styles, reading))
                reading.style_of[list_id] = top.get(_STYLE_NAME)
            if xml_id := top.get(_XML_ID):
                by_id[xml_id] = list_id
            last_of_style[top.get(_STYLE_NAME)] = list_id
        level = _level_of(paragraph)
        if level is not None:
            if level > MAX_LIST_LEVEL:
                reading.too_deep += 1
            reading.items[paragraph] = ListItem(reading.list_of[top], min(level, MAX_LIST_LEVEL))
    return reading


def _level_of(paragraph: etree._Element) -> int | None:
    """The level a paragraph is an item at, ``None`` where it is not one (a header of the list, a second paragraph
    of an item)."""
    parent = paragraph.getparent()
    if parent is None:
        return None
    if parent.tag == NUMBERED:
        return max((_positive(parent.get(_q("text", "level"))) or 1) - 1, 0)
    if parent.tag != LIST_ITEM:
        return None
    first = next(child for child in parent if child.tag in (P, H))
    if first is not paragraph:
        return None
    return sum(1 for ancestor in paragraph.iterancestors() if ancestor.tag == LIST) - 1


def can_rebuild(top: etree._Element) -> bool:
    """Can the list ``top`` be written again from paragraphs? Only when nothing but lists, items and paragraphs is in
    it: a table in an item, a header of the list or a numbered paragraph would be lost."""
    if top.tag in (P, H):
        return True

    def only_lists(element: etree._Element) -> bool:
        return all(
            child.tag in (P, H) or (child.tag in (LIST, LIST_ITEM) and only_lists(child))
            for child in element
            if isinstance(child.tag, str)
        )

    return top.tag == LIST and only_lists(top)


# -- writing ---------------------------------------------------------------------------------------------------------
def _element(local: str) -> etree._Element:
    return etree.Element(_q("text", local), nsmap={"text": NS["text"]})


def scheme_of(schemes: SchemeBook, definition: ListDef) -> Scheme:
    """The scheme a list is drawn with; one the document lost is drawn as plain numbers."""
    if definition.scheme in schemes:
        return schemes.get(definition.scheme)
    return SchemeBook().get("numbers")


class ListNames:
    """The styles and the links of the lists of a text being written, in document order: which style each list is
    drawn with, and that every list after the first piece of a list continues it. ``taken`` are the names of styles
    the file has, ``known`` the names the lists it has are drawn with (by list id), ``changed`` the lists whose
    definition is not what that style says."""

    def __init__(
        self,
        book: ListBook,
        schemes: SchemeBook,
        taken: Iterable[str] = (),
        known: dict[str, str | None] | None = None,
        changed: Iterable[str] = (),
    ) -> None:
        self.book = book
        self.schemes = schemes
        self.taken = set(taken)
        self.known = dict(known or {})
        for list_id in changed:
            self.known.pop(list_id, None)
        self.new_styles: list[bytes] = []
        self.first: dict[str, tuple[etree._Element, bool]] = {}  # the first piece of each list, and if the file has it
        self.ids = 0
        self.pending: dict[etree._Element, str] = {}

    def style(self, list_id: str) -> str:
        """The name of the list style of a list; made (and in :attr:`new_styles`) when the file has none for it."""
        if (name := self.known.get(list_id)) is not None:
            return name
        number = 0
        while f"L{number + 1}" in self.taken:
            number += 1
        name = f"L{number + 1}"
        self.taken.add(name)
        self.known[list_id] = name
        definition = self.book.get(list_id)
        self.new_styles.append(list_style(definition, scheme_of(self.schemes, definition), name))
        return name

    def start(self, list_id: str, element: etree._Element, inherit: etree._Element | None = None) -> None:
        """``element``, the next top-level ``text:list`` of the text, is of ``list_id``: give it its style and, when
        it is not the first piece of its list, what it continues. A piece that stands where another was (``inherit``)
        keeps that one's ``xml:id`` if it is the first."""
        element.set(_STYLE_NAME, self.style(list_id))
        if list_id in self.first:
            element.set(_CONTINUE_LIST, self.id_of(list_id))
            return
        self.first[list_id] = (element, False)
        if inherit is not None and (xml_id := inherit.get(_XML_ID)):
            element.set(_XML_ID, xml_id)

    def passed(self, list_id: str, top: etree._Element) -> str | None:
        """The text goes by a list element the file has and nobody writes again, of ``list_id``. What it has to
        continue: the ``xml:id`` of the first piece of the list when this is not the first one, else ``None``."""
        if list_id in self.first:
            return self.id_of(list_id)
        self.first[list_id] = (top, True)
        return None

    def id_of(self, list_id: str) -> str:
        """The ``xml:id`` of the first piece of a list, which a later piece names to continue it."""
        element, held = self.first[list_id]
        if found := element.get(_XML_ID) or self.pending.get(element):
            return found
        self.ids += 1
        xml_id = f"list{self.ids}"
        while xml_id in self.taken:
            self.ids += 1
            xml_id = f"list{self.ids}"
        self.taken.add(xml_id)
        if held:
            self.pending[element] = xml_id
        else:
            element.set(_XML_ID, xml_id)
        return xml_id

    def ids_to_add(self) -> dict[etree._Element, str]:
        """The ``xml:id`` the file's own list elements need so that the lists after them can continue them."""
        return dict(self.pending)


class ListFlow:
    """Puts paragraphs into ``parent`` the way the model says: an item into the ``text:list-item`` of a list at its
    level (the lists of the levels above it opened for it), anything else as it is, and the end of a run of items
    closes the lists. ``start`` is told about each new top-level list, to give it its style and its links."""

    def __init__(self, parent: etree._Element, start: Callable[[str, etree._Element], None]) -> None:
        self.parent = parent
        self.start = start
        self.open: list[etree._Element] = []
        self.current: str | None = None

    def add(self, paragraph: etree._Element, item: ListItem | None) -> None:
        """Put ``paragraph`` into the text, as an item of a list when ``item`` says so."""
        if item is None:
            self.close()
            self.parent.append(paragraph)
            return
        if item.list != self.current:
            self.close()
            top = _element("list")
            self.start(item.list, top)
            self.parent.append(top)
            self.open, self.current = [top], item.list
        while len(self.open) > item.level + 1:
            self.open.pop()
        while len(self.open) < item.level + 1:
            holder = self.open[-1][-1] if len(self.open[-1]) else etree.SubElement(self.open[-1], LIST_ITEM)
            nested = etree.SubElement(holder, LIST)
            self.open.append(nested)
        etree.SubElement(self.open[-1], LIST_ITEM).append(paragraph)

    def close(self) -> None:
        """No more items of the list that is open."""
        self.open, self.current = [], None


# -- numbered headings: the outline style ----------------------------------------------------------------------------
OUTLINE_STYLE = _q("text", "outline-style")
#: The levels an outline has in OpenDocument; the model's headings go down to MAX_LIST_LEVEL + 1.
_OUTLINE_LEVELS = 10


def heading_list(styles: StyleBook) -> str | None:
    """The list the heading styles are numbered in: an odt numbers its headings with one outline, so the list most
    heading styles name (the first one, on a tie)."""
    counted: dict[str, int] = {}
    for style in styles:
        level = styles.heading_level(style.id) if style.kind == "paragraph" else None
        numbering = styles.numbering(style.id) if level else None
        if numbering is not None:
            counted[numbering] = counted.get(numbering, 0) + 1
    return max(counted, key=lambda list_id: counted[list_id]) if counted else None


def outline_style(styles: StyleBook, lists: ListBook, schemes: SchemeBook) -> bytes:
    """The ``text:outline-style`` that numbers the headings of the text as the model does: each outline level as the
    level below it of the scheme of :func:`heading_list` (heading 1 at the scheme's first level); every level unnumbered
    when no heading style is numbered. It declares its prefixes, so that it can go into any part."""
    list_id = heading_list(styles)
    definition = lists.get(list_id) if list_id is not None and list_id in lists else None
    scheme = scheme_of(schemes, definition) if definition is not None else None
    declared = " ".join(f'xmlns:{prefix}="{NS[prefix]}"' for prefix in ("text", "style"))
    levels = []
    for number in range(_OUTLINE_LEVELS):
        if scheme is None or number > MAX_LIST_LEVEL:
            levels.append(f'<text:outline-level-style text:level="{number + 1}" style:num-format=""/>')
            continue
        start = definition.start if number == 0 and definition is not None and definition.start != 1 else None
        levels.append(level_style("outline-level-style", scheme.level(number), number, "", start))
    return f'<text:outline-style {declared} style:name="Outline">{"".join(levels)}</text:outline-style>'.encode()


def read_outline(roots: Iterable[etree._Element], lists: ListBook, schemes: SchemeBook) -> str | None:
    """The list an odt numbers its headings in, added to ``lists`` (its scheme to ``schemes`` if it needs one of its
    own); ``None`` when the file's outline numbers nothing or says something the model cannot."""
    style = next((found for root in roots for found in root.iter(OUTLINE_STYLE)), None)
    if style is None:
        return None
    if not any(level.get(_q("style", "num-format")) for level in style.iter(OUTLINE_LEVEL)):
        return None  # every level unnumbered: what a program writes for headings that are not numbered
    levels = {n: level for n, level in read_levels(style, {OUTLINE_LEVEL}).items() if n <= MAX_LIST_LEVEL}
    scheme = scheme_for(levels, True, "Outline", schemes)
    if scheme is None:
        return None
    first = next((e for e in style.iter(OUTLINE_LEVEL) if e.get(_q("text", "level")) == "1"), None)
    start = _positive(first.get(_q("text", "start-value")) if first is not None else None) or 1
    list_id = "outline" if "outline" not in lists else lists.unique_id()
    lists.add(ListDef(list_id, scheme, min(start, 999_999), "Outline"))
    return list_id
