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
* The scheme of a list is that of the first level of its style: a number format is ``numbers``, a bullet or a picture
  is ``bullets``. A style whose levels do not look like the scheme's (another number format, another bullet) is
  reported as ``list-look``: the model shows its own markers, and the file keeps its own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from lxml import etree

from claudia_core import MAX_LIST_LEVEL, SCHEMES, ListBook, ListDef, ListItem
from claudia_odf_io import NS

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
_LEVEL_STYLES = {_q("text", name): name for name in ("list-level-style-number", "list-level-style-bullet")}
#: What the model draws at each level: the number format and the bullet sign, repeating every three levels.
_NUMBER_FORMATS = ("1", "a", "i")
_BULLET_SIGNS = ("•", "◦", "▪")
#: How far each level moves the text in (a scheme says it in em; a list style wants a length).
_CM_PER_EM = 0.4


# -- the style of a list --------------------------------------------------------------------------------------------
def list_style(definition: ListDef, name: str) -> bytes:
    """The ``text:list-style`` that makes a list of the model look as the model draws it: ``name`` is what the lists
    in the text call it, and every level (the model has nine) its marker and its indent. It declares the prefixes
    it uses, so that it can go into a part that does not."""
    scheme = SCHEMES[definition.scheme]
    step = f"{round(scheme.indent * _CM_PER_EM, 3):g}"
    declared = " ".join(f'xmlns:{prefix}="{NS[prefix]}"' for prefix in ("text", "style", "fo"))
    display = f' style:display-name="{_attribute(definition.name)}"' if definition.name else ""
    levels = []
    for level in range(MAX_LIST_LEVEL + 1):
        indent = f"{round(scheme.indent * _CM_PER_EM * (level + 1), 3):g}"
        position = (
            '<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">'
            f'<style:list-level-label-alignment text:label-followed-by="listtab" '
            f'text:list-tab-stop-position="{indent}cm" fo:text-indent="-{step}cm" fo:margin-left="{indent}cm"/>'
            "</style:list-level-properties>"
        )
        if scheme.counts:
            start = f' text:start-value="{definition.start}"' if level == 0 and definition.start != 1 else ""
            levels.append(
                f'<text:list-level-style-number text:level="{level + 1}" style:num-suffix="." '
                f'style:num-format="{_NUMBER_FORMATS[level % 3]}"{start}>{position}</text:list-level-style-number>'
            )
        else:
            levels.append(
                f'<text:list-level-style-bullet text:level="{level + 1}" text:bullet-char="{_BULLET_SIGNS[level % 3]}">'
                f"{position}</text:list-level-style-bullet>"
            )
    return f'<text:list-style {declared} style:name="{name}"{display}>{"".join(levels)}</text:list-style>'.encode()


def _attribute(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


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


def _look_differs(style: etree._Element, scheme: str) -> bool:
    """Does a level of ``style`` draw something other than the model's scheme would?"""
    for level in style:
        if level.tag not in _LEVEL_STYLES:
            continue
        number = _positive(level.get(_q("text", "level")))
        if number is None or number > MAX_LIST_LEVEL + 1:
            continue
        index = (number - 1) % 3
        if scheme == "numbers":
            if (
                level.tag != _q("text", "list-level-style-number")
                or level.get(_q("style", "num-format")) != _NUMBER_FORMATS[index]
                or level.get(_q("style", "num-suffix")) != "."
                or level.get(_q("style", "num-prefix"))
                or level.get(_q("text", "display-levels"), "1") != "1"
            ):
                return True
        elif (
            level.tag != _q("text", "list-level-style-bullet")
            or level.get(_q("text", "bullet-char")) != (_BULLET_SIGNS[index])
        ):
            return True
    return False


# -- reading ---------------------------------------------------------------------------------------------------------
@dataclass
class ListReading:
    """What the paragraphs of a text say about lists."""

    book: ListBook = field(default_factory=ListBook)
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
    scheme = "numbers" if level is not None and level.tag == _q("text", "list-level-style-number") else "bullets"
    start = 1
    if scheme == "numbers":
        start = _positive(level.get(_q("text", "start-value")) if level is not None else None) or 1
        item = top.find(LIST_ITEM)
        start = _positive(item.get(_q("text", "start-value")) if item is not None else None) or start
    display = style.get(_q("style", "display-name")) if style is not None else None
    name = display if display and display.strip() and len(display) <= 60 and display.isprintable() else None
    if style is None or _look_differs(style, scheme):
        reading.odd_looks += 1
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


class ListNames:
    """The styles and the links of the lists of a text being written, in document order: which style each list is
    drawn with, and that every list after the first piece of a list continues it. ``taken`` are the names of styles
    the file has, ``known`` the names the lists it has are drawn with (by list id), ``changed`` the lists whose
    definition is not what that style says."""

    def __init__(
        self,
        book: ListBook,
        taken: Iterable[str] = (),
        known: dict[str, str | None] | None = None,
        changed: Iterable[str] = (),
    ) -> None:
        self.book = book
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
        self.new_styles.append(list_style(self.book.get(list_id), name))
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
