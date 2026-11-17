"""Lists in the text boxes of a presentation, in a pptx and an odp (E9.21, E9.22; step D of
``claudiaoffice-log/notes/text-structure-across-apps.md``).

In the model a list runs on from one text box to the next across slides, and a slide title can be numbered by its
style; the markers are derived, never characters of the words. The two formats hold it differently:

* **pptx** numbers within one text body: a box's first paragraph gets ``a:buAutoNum`` (with ``startAt`` where the
  count goes on from an earlier box) or ``a:buChar``, and ``lvl`` for its level. A marker PowerPoint has no automatic
  number for (a trail such as ``2.1``, text around a number other than its few forms) is not written; it is reported
  as ``list-look``. Read back, a numbered box whose ``startAt`` goes on from the last box of the same look continues
  that list; any other starts a new one.
* An **agenda** (a text box whose words are generated, E9.31) is written as the lines it shows, each "number title
  slide"; neither format can derive it, so it no longer follows the slides once written: the loss ``agenda``. Read
  back it is a text box with those words.
* **odp** has lists that continue across text boxes as they do across paragraphs (``xml:id`` and
  ``text:continue-list``), and list styles that say every level (:mod:`claudia_odf_io.lists`). A box's paragraphs are
  the item of a ``text:list``, nested for its level.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from claudia_core import (
    Label,
    LevelFormat,
    ListBook,
    ListDef,
    ListItem,
    Scheme,
    SchemeBook,
    builtin_scheme,
)
from claudia_creates import SlideModel
from claudia_odf_io import LEVEL_BULLET, LEVEL_NUMBER, NS, list_style, read_levels
from claudia_odf_io.lists import counts

ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"
#: The automatic numbers PowerPoint has, by what a level of the model draws: (format, before, after).
AUTONUM = {
    (form, before, after): f"{name}{suffix}"
    for form, name in (
        ("decimal", "arabic"),
        ("lower-alpha", "alphaLc"),
        ("upper-alpha", "alphaUc"),
        ("lower-roman", "romanLc"),
        ("upper-roman", "romanUc"),
    )
    for (before, after), suffix in ((("", "."), "Period"), (("", ")"), "ParenR"), (("(", ")"), "ParenBoth"))
} | {("decimal", "", ""): "arabicPlain"}
_FROM_AUTONUM = {name: key for key, name in AUTONUM.items()}
#: How far a level moves the words of a box in, in EMU (PowerPoint's own step).
_STEP = 342_900
#: What may follow the bullet in an ``a:pPr`` (the schema's order).
_AFTER_BULLET = ("tabLst", "defRPr", "extLst")
_BULLETS = ("buNone", "buAutoNum", "buChar", "buBlip", "buFont", "buFontTx")


def _a(local: str) -> str:
    return f"{{{ANS}}}{local}"


@dataclass(frozen=True)
class Mark:
    """What is drawn before the words of one object: its list, level, the level's look and the label."""

    list: str
    level: int
    look: LevelFormat
    label: Label
    scheme: Scheme


def marks_of(model: SlideModel) -> dict[str, Mark]:
    """The mark of every object whose words are a list item or a numbered title, by object id."""
    labels = model.labels()
    marks: dict[str, Mark] = {}
    for paragraph, item in model.structure.items():
        if item is None or paragraph not in labels:
            continue
        scheme = model.schemes.get(model.lists.get(item.list).scheme)
        marks[paragraph] = Mark(item.list, item.level, scheme.level(item.level), labels[paragraph], scheme)
    return marks


# -- agendas -------------------------------------------------------------------------------------------------------
def agenda_lines(model: SlideModel, object_id: str) -> str:
    """What an agenda shows, as lines of text: each entry's number, its words and, after a tab, its slide."""
    toc = model.generated_of(object_id)
    lines = []
    for entry in model.structure.entries(object_id):
        words = f"{entry.number} {entry.text}" if entry.number else entry.text
        lines.append(f"{words}\t{entry.place}" if toc is not None and toc.places and entry.place else words)
    return "\n".join(lines)


def words_of(model: SlideModel, body: object) -> str:
    """The words a format writes for an object: its own, or for an agenda the lines it shows."""
    paragraph = getattr(body, "paragraph", None)
    if paragraph is None:
        return ""
    return agenda_lines(model, body.id) if paragraph.generated is not None else paragraph.text  # type: ignore[attr-defined]


def agendas(model: SlideModel) -> int:
    """How many agendas the presentation has (each is written as text: the loss ``agenda``)."""
    return sum(1 for obj in model.objects.values() if obj.body.paragraph is not None and obj.body.paragraph.generated)


# -- pptx ------------------------------------------------------------------------------------------------------------
def write_pptx_mark(paragraph: etree._Element, mark: Mark | None) -> bool:
    """Give an ``a:p`` the bullet or automatic number of ``mark`` (none: no bullet). ``False`` when PowerPoint cannot
    draw the marker; the paragraph then gets none."""
    properties = paragraph.find(_a("pPr"))
    if properties is None:
        properties = etree.Element(_a("pPr"))
        paragraph.insert(0, properties)
    for old in [child for child in properties if etree.QName(child).localname in _BULLETS]:
        properties.remove(old)
    for name in ("lvl", "marL", "indent"):
        if name in properties.attrib:
            del properties.attrib[name]
    if mark is None:
        return True
    look = mark.look
    if not sayable_in_pptx(mark):
        return False
    if look.format == "bullet":
        bullet = etree.Element(_a("buChar"), {"char": look.bullet})
    else:
        bullet = etree.Element(_a("buAutoNum"), {"type": AUTONUM[(look.format, look.before, look.after)]})
        number = mark.label.path[-1] if mark.label.path else 1
        if number != 1:
            bullet.set("startAt", str(number))
    if mark.level:
        properties.set("lvl", str(mark.level))
    properties.set("marL", str(_STEP * (mark.level + 1)))
    properties.set("indent", str(-_STEP))
    later = next((c for c in properties if etree.QName(c).localname in _AFTER_BULLET), None)
    if later is not None:
        later.addprevious(bullet)
    else:
        properties.append(bullet)
    return True


def read_pptx_mark(paragraph: etree._Element) -> tuple[int, LevelFormat, int | None] | None:
    """The level, the look and the ``startAt`` of the bullet or automatic number of an ``a:p``; ``None`` for none, or
    for one the model cannot draw (a picture bullet, an automatic number it has no format for)."""
    properties = paragraph.find(_a("pPr"))
    if properties is None:
        return None
    try:
        level = min(max(int(properties.get("lvl") or 0), 0), 8)
    except ValueError:
        level = 0
    sign = properties.find(_a("buChar"))
    if sign is not None:
        char = sign.get("char") or ""
        return (level, LevelFormat("bullet", char, from_level=level), None) if 1 <= len(char) <= 4 else None
    number = properties.find(_a("buAutoNum"))
    if number is None or number.get("type") not in _FROM_AUTONUM:
        return None
    form, before, after = _FROM_AUTONUM[number.get("type", "")]
    try:
        start = int(number.get("startAt") or 1)
    except ValueError:
        start = 1
    return level, LevelFormat(form, before=before, after=after, from_level=level), start


@dataclass
class ItemReader:
    """Turns the marks read box by box, in reading order, into items of lists: a numbered box that counts on from the
    last one of the same look continues its list, as do deeper levels and bullets of that look."""

    lists: ListBook = field(default_factory=ListBook)
    schemes: SchemeBook = field(default_factory=SchemeBook)
    _open: dict[str, str] = field(default_factory=dict)  # the list open for each scheme
    _count: dict[str, int] = field(default_factory=dict)  # how many first-level items each list has

    def item(self, level: int, look: LevelFormat, start: int | None) -> ListItem:
        """The item of the next marked box."""
        counts = look.counts or look.format == "none"
        scheme = self.schemes.drawing({level: look}, counts) or ("numbers" if counts else "bullets")
        list_id = self._open.get(scheme)
        goes_on = level > 0 or not counts or (start is not None and start == self._count.get(list_id or "", 0) + 1)
        if list_id is None or not goes_on:
            list_id = self.lists.unique_id()
            first = start if counts and level == 0 and start else 1
            self.lists.add(ListDef(list_id, scheme, min(first, 999_999)))
            self._open[scheme] = list_id
            self._count[list_id] = first - 1
        if level == 0:
            self._count[list_id] = self._count.get(list_id, 0) + 1
        return ListItem(list_id, level)


# -- odp -------------------------------------------------------------------------------------------------------------
def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


LIST, LIST_ITEM = _q("text", "list"), _q("text", "list-item")
_STYLE_NAME, _CONTINUE_LIST, _XML_ID = _q("text", "style-name"), _q("text", "continue-list"), f"{{{NS['xml']}}}id"


@dataclass
class OdpLists:
    """The list styles and the links of the lists of a presentation being written: one list style per list, and every
    box after the first of a list continues it."""

    model: SlideModel
    styles: list[bytes] = field(default_factory=list)
    _names: dict[str, str] = field(default_factory=dict)  # list id -> style name
    _first: dict[str, str] = field(default_factory=dict)  # list id -> the xml:id of its first piece

    def wrap(self, paragraphs: list[etree._Element], mark: Mark) -> etree._Element:
        """The ``text:list`` that makes ``paragraphs`` the item of the list of ``mark``, at its level."""
        top = etree.Element(LIST)
        if mark.list not in self._names:
            name = f"L{len(self._names) + 1}"
            self._names[mark.list] = name
            self.styles.append(list_style(self.model.lists.get(mark.list), mark.scheme, name))
        top.set(_STYLE_NAME, self._names[mark.list])
        if mark.list in self._first:
            top.set(_CONTINUE_LIST, self._first[mark.list])
        else:
            self._first[mark.list] = f"list{len(self._first) + 1}"
            top.set(_XML_ID, self._first[mark.list])
        holder = etree.SubElement(top, LIST_ITEM)
        for _ in range(mark.level):
            holder = etree.SubElement(etree.SubElement(holder, LIST), LIST_ITEM)
        holder.extend(paragraphs)
        return top


def odp_level(paragraph: etree._Element, owner: etree._Element) -> tuple[etree._Element, int] | None:
    """The top-level ``text:list`` a paragraph of ``owner`` is the first paragraph of an item of, and its level."""
    parent = paragraph.getparent()
    if parent is None or parent.tag != LIST_ITEM or next(iter(parent), None) is not paragraph:
        return None
    level, top = -1, parent
    found = paragraph
    while (up := found.getparent()) is not None and up is not owner:
        if up.tag == LIST:
            level, top = level + 1, up
        found = up
    return top, max(level, 0)


@dataclass
class OdpListReader:
    """The lists of the boxes of an odp: a ``text:list`` that continues another (``text:continue-list``) is that list;
    any other is a new one, drawn with the scheme its list style says (a look the model cannot say: the built-in
    scheme of its kind)."""

    styles: dict[str, etree._Element]
    lists: ListBook = field(default_factory=ListBook)
    schemes: SchemeBook = field(default_factory=SchemeBook)
    odd_looks: int = 0
    _by_xml_id: dict[str, str] = field(default_factory=dict)

    def item(self, top: etree._Element, level: int) -> ListItem:
        """The item a box is whose first paragraph is in the list ``top`` at ``level``."""
        follows = top.get(_CONTINUE_LIST)
        list_id = self._by_xml_id.get(follows or "")
        if list_id is None:
            list_id = self._new(top)
        if xml_id := top.get(_XML_ID):
            self._by_xml_id[xml_id] = list_id
        return ListItem(list_id, min(level, 8))

    def _new(self, top: etree._Element) -> str:
        style = self.styles.get(top.get(_STYLE_NAME) or "")
        numbered = counts(style)
        levels = read_levels(style, (LEVEL_NUMBER, LEVEL_BULLET)) if style is not None else {0: None}
        scheme = None
        if all(level is not None for level in levels.values()):
            scheme = self.schemes.drawing({n: lv for n, lv in levels.items() if lv is not None}, numbered)
        if scheme is None:
            self.odd_looks += 1
            fallback = builtin_scheme("numbers" if numbered else "bullets")
            assert fallback is not None  # a built-in scheme
            scheme = fallback.id
        first = next((e for e in style if e.get(_q("text", "level")) == "1"), None) if style is not None else None
        try:
            start = int(first.get(_q("text", "start-value")) or 1) if first is not None else 1
        except ValueError:
            start = 1
        list_id = self.lists.unique_id()
        self.lists.add(ListDef(list_id, scheme, min(max(start, 1), 999_999)))
        return list_id


def list_styles(*roots: etree._Element | None) -> dict[str, etree._Element]:
    """Every ``text:list-style`` of the file, by name."""
    found: dict[str, etree._Element] = {}
    for root in roots:
        for style in root.iter(_q("text", "list-style")) if root is not None else ():
            if name := style.get(_q("style", "name")):
                found.setdefault(name, style)
    return found


def sayable_in_pptx(mark: Mark) -> bool:
    """Can PowerPoint draw this marker (a bullet, or an automatic number of its own level)?"""
    look = mark.look
    if look.format == "bullet":
        return not (look.before or look.after)
    return look.counts and look.from_level == mark.level and (look.format, look.before, look.after) in AUTONUM
