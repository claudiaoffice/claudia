"""Converting between a :class:`~claudia_composes.TextModel` and OpenDocument text (odt) (D401, D402).

This is the first of the three OpenDocument formats (D70: odt, then odp, then ods) and it keeps the promise D217
made for docx, further: **maximum preservation from day one**. Three things follow from that.

* ``text_to_odt`` writes a model as a new file, and ``odt_export_losses`` says what the file cannot hold.
* ``odt_to_text`` reads the paragraphs of a file as a model, and ``odt_import_losses`` says what the model does not
  show (tables, pictures, notes, formatting...). Nothing is thrown away by reading: the file is not changed.
* ``apply_edits_to_odt`` is the way back for an *edited* import: it patches what changed since the baseline onto the
  bytes of the original file, so a table, a footnote or a style the text app does not model is still there, and
  every byte outside the paragraphs that were edited is the original's -- the other parts of the package are
  untouched. Blocks can be added, removed and restyled, and an open suggestion becomes a tracked change.

What the model sees of an odt is its paragraphs: every ``text:p`` and ``text:h`` in the flow of the text, also the
ones in lists and sections (their structure stays in the file), but not the ones in tables, which are cells and not
text of the flow. The id of a block is its place in that order (``b1``, ``b2``...), so a baseline and the file it was
read from agree without the file having to carry ids.

Styles are mapped by name only (D401): Title, Heading 1, Heading 2 and Quotations go to and from the styles of the
same name; every other style is body text -- and named in the losses, so that nobody believes it was kept.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import count
from zipfile import BadZipFile

from lxml import etree

from claudia_composes import DEFAULT_STYLE, Block, Run, Suggestion, TextModel
from claudia_odf_io import (
    MIME,
    NS,
    VERSION,
    DocumentInfo,
    Loss,
    LossLog,
    OdfError,
    XmlPart,
    decode_style_name,
    hidden_content,
    insert_elements,
    new_meta,
    new_package,
    read_text,
    set_text,
    update_package_meta,
    xml_safe,
)
from claudia_opc_io import read_parts, write_parts

from ._suggestions import WhenMade, open_replacements, when_made
from .docx import UnsupportedEdit

_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
#: What a tracked change is dated when nobody knows when its suggestion was made (the model keeps no time; the server
#: reads it from the log and passes it in, D411), since a program needs a date before it reads the change at all
#: (LibreOffice drops one without): the earliest date there is, the way it writes a change from a file with no date.
_NO_DATE = "1970-01-01T00:00:00"
_DEFAULT_AUTHOR = "Claudia AI"


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


_P, _H = _q("text", "p"), _q("text", "h")
_STYLE_NAME, _OUTLINE = _q("text", "style-name"), _q("text", "outline-level")

#: The built-in styles (``model.py``'s ``BUILTIN_STYLES``) by the name of the OpenDocument style they are written as;
#: body text, and every style not in this table, is written as "Standard".
_ODF_NAME = {"title": "Title", "heading-1": "Heading_20_1", "heading-2": "Heading_20_2", "quote": "Quotations"}
_LEVEL = {"heading-1": 1, "heading-2": 2}
_STANDARD = "Standard"
#: Names of styles of body text, which become body text without a word about it.
_BODY_NAMES = ("Standard", "Text_20_body", "Text_20_Body", "Body_20_Text", "Default_20_Paragraph_Style")
_KNOWN = {
    "Title": "title",
    "Heading_20_1": "heading-1",
    "Heading_20_2": "heading-2",
    "Quotations": "quote",
    "Quote": "quote",
    **dict.fromkeys(_BODY_NAMES, DEFAULT_STYLE),
}
_INDEXES = {
    _q("text", name)
    for name in (
        "table-of-content",
        "illustration-index",
        "table-index",
        "object-index",
        "user-index",
        "alphabetical-index",
        "bibliography",
    )
}
#: What holds paragraphs and is part of the flow of the text, not a thing of its own.
_FLOW = {_q("text", name) for name in ("section", "list", "list-item", "list-header", "numbered-paragraph")}
_LIST_PARTS = {_q("text", name) for name in ("list", "list-item", "list-header", "numbered-paragraph")}
_TABLE = _q("table", "table")

#: The definition of each style the app writes, for a new file and for one that has no style of the name.
_STYLE_XML = {
    "Standard": '<style:style style:name="Standard" style:family="paragraph" style:class="text">'
    '<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.25cm"/></style:style>',
    "Title": '<style:style style:name="Title" style:family="paragraph" style:next-style-name="Standard" '
    'style:class="chapter"><style:paragraph-properties fo:margin-top="0.423cm" fo:margin-bottom="0.212cm" '
    'fo:text-align="center"/><style:text-properties fo:font-size="28pt" fo:font-weight="bold"/></style:style>',
    "Heading_20_1": '<style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" '
    'style:next-style-name="Standard" style:default-outline-level="1" style:class="text">'
    '<style:paragraph-properties fo:margin-top="0.423cm" fo:margin-bottom="0.212cm" fo:keep-with-next="always"/>'
    '<style:text-properties fo:font-size="18pt" fo:font-weight="bold"/></style:style>',
    "Heading_20_2": '<style:style style:name="Heading_20_2" style:display-name="Heading 2" style:family="paragraph" '
    'style:next-style-name="Standard" style:default-outline-level="2" style:class="text">'
    '<style:paragraph-properties fo:margin-top="0.353cm" fo:margin-bottom="0.212cm" fo:keep-with-next="always"/>'
    '<style:text-properties fo:font-size="14pt" fo:font-weight="bold"/></style:style>',
    "Quotations": '<style:style style:name="Quotations" style:family="paragraph" style:class="html">'
    '<style:paragraph-properties fo:margin-left="1cm" fo:margin-right="1cm" fo:margin-top="0cm" '
    'fo:margin-bottom="0.25cm"/><style:text-properties fo:font-style="italic"/></style:style>',
}
_NS_DECLS = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items() if prefix != "xml")


# -- what is in a file ---------------------------------------------------------------------------------------------
def _read(data: bytes) -> dict[str, bytes]:
    """The parts of an odt file, or an ``OdfError`` saying why it is not one."""
    try:
        parts = read_parts(data)
    except BadZipFile as problem:
        raise OdfError("this is not an OpenDocument file: it is not a zip file") from problem
    kind = parts.get("mimetype")
    if kind is None or not kind.startswith(b"application/vnd.oasis.opendocument."):
        raise OdfError("this is not an OpenDocument file: it has no mimetype")
    if kind.strip() != MIME["text"].encode():
        raise OdfError("this OpenDocument file is not a text document")
    if "content.xml" not in parts:
        raise OdfError("this is not an OpenDocument file: it has no content.xml")
    return parts


def _text_body(root: etree._Element) -> etree._Element:
    found = root.find("office:body/office:text", NS)
    if found is None:
        raise OdfError("this OpenDocument file is not a text document: its content has no text")
    return found


@dataclass
class _Scan:
    """What the flow of a text holds: the paragraphs that are blocks, and what is in it that is not."""

    paragraphs: list[etree._Element]
    tables: int = 0
    lists: int = 0
    indexes: int = 0
    frames: int = 0


def _scan(body: etree._Element) -> _Scan:
    found = _Scan([])

    def visit(parent: etree._Element) -> None:
        for child in parent:
            tag = child.tag
            if not isinstance(tag, str):
                continue
            if tag in (_P, _H):
                found.paragraphs.append(child)
            elif tag in _FLOW:
                if tag == _q("text", "list") and parent.tag not in _LIST_PARTS:
                    found.lists += 1
                visit(child)
            elif tag == _TABLE:
                found.tables += 1
            elif tag in _INDEXES:
                found.indexes += 1
            elif tag.startswith(f"{{{NS['draw']}}}"):
                found.frames += 1

    visit(body)
    return found


def _paragraph_styles(*roots: etree._Element) -> dict[str, str | None]:
    """Every paragraph style of the file with the style it is based on."""
    out: dict[str, str | None] = {}
    for root in roots:
        for style in root.iter(_q("style", "style")):
            name = style.get(_q("style", "name"))
            if name and style.get(_q("style", "family")) == "paragraph":
                out[name] = style.get(_q("style", "parent-style-name"))
    return out


def _resolved(name: str | None, parents: dict[str, str | None]) -> str | None:
    """The style of the text app that the style ``name`` is, or is based on; ``None`` if it is none."""
    seen: set[str] = set()
    while name and name not in seen:
        if name in _KNOWN:
            return _KNOWN[name]
        seen.add(name)
        name = parents.get(name)
    return None


def _level(paragraph: etree._Element) -> int:
    try:
        return int(paragraph.get(_OUTLINE) or 1)
    except ValueError:
        return 1


def _style_of(paragraph: etree._Element, parents: dict[str, str | None], losses: LossLog | None) -> str:
    name = paragraph.get(_STYLE_NAME)
    found = _resolved(name, parents)
    if paragraph.tag == _H and found in (None, DEFAULT_STYLE):
        level = _level(paragraph)
        for style_id, wanted in _LEVEL.items():
            if wanted == level:
                return style_id
        if losses is not None:
            losses.add("heading-level", str(level))
        return DEFAULT_STYLE
    if found is None:
        if name and losses is not None:
            losses.add("style", decode_style_name(name))
        return DEFAULT_STYLE
    return found


def _open_styles(parts: dict[str, bytes], content: etree._Element) -> dict[str, str | None]:
    styles = etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else content
    return _paragraph_styles(styles, content)


def _document(data: bytes) -> tuple[dict[str, bytes], etree._Element, _Scan, dict[str, str | None]]:
    parts = _read(data)
    try:
        content = etree.fromstring(parts["content.xml"], etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as problem:
        raise OdfError(f"content.xml of this file is not well-formed XML: {problem}") from problem
    body = _text_body(content)
    return parts, body, _scan(body), _open_styles(parts, content)


def odt_to_text(odt_bytes: bytes) -> TextModel:
    """``odt_bytes`` as a :class:`~claudia_composes.TextModel`: one block per paragraph of the flow, in order,
    called ``b1``, ``b2``... by its place. Title, Heading 1, Heading 2 and Quotations (or a style based on one) map to
    the styles of the text app and anything else is body text; what the model does not show is in
    :func:`odt_import_losses`. Raises :class:`~claudia_odf_io.OdfError` for a file that is not an odt."""
    _, _, scan, parents = _document(odt_bytes)
    blocks = []
    for number, paragraph in enumerate(scan.paragraphs, start=1):
        text = read_text(paragraph)
        blocks.append(
            Block(f"b{number}", _style_of(paragraph, parents, None), text, (Run(len(text), None),) if text else ())
        )
    return TextModel(blocks) if blocks else TextModel()


def odt_import_losses(odt_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`odt_to_text` does not show of the file, each as a code (``"table"``, ``"footnote"``,
    ``"formatting"``...) with how many there are, in the order they come. None of it is lost from the *file*: an
    edit that is exported with :func:`apply_edits_to_odt` keeps all of it."""
    parts, body, scan, parents = _document(odt_bytes)
    losses = LossLog()
    hidden: dict[str, int] = {}
    formatting = links = 0
    for paragraph in scan.paragraphs:
        _style_of(paragraph, parents, losses)
        for kind in hidden_content(paragraph):
            hidden[kind] = hidden.get(kind, 0) + 1
        formatting += sum(1 for span in paragraph.iter(_q("text", "span")) if span.get(_STYLE_NAME))
        links += sum(1 for _ in paragraph.iter(_q("text", "a")))
    for code, number in (
        ("table", scan.tables),
        ("list", scan.lists),
        ("index", scan.indexes),
        ("frame", scan.frames),
        ("formatting", formatting),
        ("link", links),
        ("tracked-change", sum(1 for _ in body.iter(_q("text", "changed-region")))),
    ):
        if number:
            losses.add(code, count=number)
    for kind, number in hidden.items():
        losses.add(kind, count=number)
    return losses.result()


# -- tracked changes -----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Change:
    """One tracked change to write: a deletion of ``text`` at the place ``at`` of the paragraph, or the insertion of
    what is in the paragraph between ``at`` and ``end``."""

    kind: str
    author: str
    at: int
    end: int
    date: str
    text: str = ""


def _plan(text: str, suggestions: list[Suggestion], when: WhenMade | None = None) -> tuple[str, list[_Change], int]:
    """The text a paragraph with these suggestions has (their replacements in, what they replace out), the changes to
    write for them, and how many suggestions could not be placed because their anchor no longer matches the text."""
    out, changes, position, skipped = "", [], 0, 0
    for suggestion in suggestions:
        start, end = suggestion.anchor.start, suggestion.anchor.end
        if start < position or end > len(text):
            skipped += 1
            continue
        out += text[position:start]
        author = suggestion.author or _DEFAULT_AUTHOR
        date = (when(suggestion) if when else None) or _NO_DATE
        if end > start:
            changes.append(_Change("deletion", author, len(out), len(out), date, text[start:end]))
        if suggestion.replacement:
            replacement = xml_safe(suggestion.replacement)
            changes.append(_Change("insertion", author, len(out), len(out) + len(replacement), date))
            out += replacement
        position = end
    return out + text[position:], changes, skipped


def _element(prefix: str, local: str, **attributes: str) -> etree._Element:
    element = etree.Element(_q(prefix, local), nsmap={prefix: NS[prefix]})
    for key, value in attributes.items():
        element.set(_q(prefix, key.replace("_", "-")), value)
    return element


def _region(change: _Change, change_id: str, style_name: str) -> etree._Element:
    region = etree.Element(
        _q("text", "changed-region"), nsmap={"text": NS["text"], "office": NS["office"], "dc": NS["dc"]}
    )
    region.set(_q("text", "id"), change_id)
    region.set(f"{{{NS['xml']}}}id", change_id)
    holder = etree.SubElement(region, _q("text", change.kind))
    info = etree.SubElement(holder, _q("office", "change-info"))
    etree.SubElement(info, _q("dc", "creator")).text = change.author
    etree.SubElement(info, _q("dc", "date")).text = change.date
    if change.kind == "deletion":
        deleted = etree.SubElement(holder, _P)
        deleted.set(_STYLE_NAME, style_name)
        set_text(deleted, change.text)
    return region


def _write_changes(
    paragraph: etree._Element, changes: list[_Change], ids: Iterator[str], style_name: str
) -> list[etree._Element]:
    """Put the marks of ``changes`` into ``paragraph`` and return the regions that go with them."""
    regions, marks = [], []
    for change in changes:
        change_id = next(ids)
        regions.append(_region(change, change_id, style_name))
        if change.kind == "deletion":
            marks.append((change.at, _element("text", "change", change_id=change_id)))
        else:
            marks.append((change.at, _element("text", "change-start", change_id=change_id)))
            marks.append((change.end, _element("text", "change-end", change_id=change_id)))
    insert_elements(paragraph, marks)
    return regions


def _ids(used: set[str]) -> Iterator[str]:
    for number in count(1):
        if f"ct{number}" not in used:
            yield f"ct{number}"


# -- writing a paragraph ---------------------------------------------------------------------------------------------
def _new_paragraph(
    style_id: str, text: str, suggestions: list[Suggestion], ids: Iterator[str], when: WhenMade
) -> tuple[etree._Element, list[etree._Element]]:
    """A paragraph element for a block, and the tracked-change regions of its suggestions."""
    name = _ODF_NAME.get(style_id, _STANDARD)
    level = _LEVEL.get(style_id)
    paragraph = etree.Element(_H if level else _P, nsmap={"text": NS["text"]})
    paragraph.set(_STYLE_NAME, name)
    if level:
        paragraph.set(_OUTLINE, str(level))
    body, changes, _ = _plan(text, suggestions, when)
    set_text(paragraph, body)
    return paragraph, _write_changes(paragraph, changes, ids, name)


# -- export ----------------------------------------------------------------------------------------------------------
def _styles_part() -> bytes:
    styles = "".join(_STYLE_XML[name] for name in ("Standard", "Title", "Heading_20_1", "Heading_20_2", "Quotations"))
    return (
        f'{_DECLARATION}<office:document-styles {_NS_DECLS} office:version="{VERSION}">'
        f"<office:styles>{styles}</office:styles>"
        '<office:automatic-styles><style:page-layout style:name="pm1"><style:page-layout-properties '
        'fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="2cm" '
        'fo:margin-bottom="2cm" fo:margin-left="2cm" fo:margin-right="2cm"/></style:page-layout>'
        "</office:automatic-styles>"
        "<office:master-styles>"
        '<style:master-page style:name="Standard" style:page-layout-name="pm1"/>'
        "</office:master-styles>"
        "</office:document-styles>"
    ).encode()


def text_to_odt(
    model: TextModel,
    *,
    track_suggestions: bool = True,
    info: DocumentInfo | None = None,
    change_times: Mapping[str, str] | None = None,
) -> bytes:
    """``model`` as odt bytes: one paragraph (or heading) per block, the built-in styles written as the styles of the
    same name. When ``track_suggestions`` (the default), every open suggestion that proposes a replacement is written
    as a tracked change a reviewer can accept or reject in any OpenDocument program; a remark has no text to track and
    is left out, as is one that is resolved or withdrawn. Anything else not in the file is in
    :func:`odt_export_losses`.

    ``info`` is what the file says about the document in ``meta.xml`` (title, who made it and when, who saved it last
    and when). ``change_times`` has when each suggestion was made, by id, and dates its tracked change; one it has no
    time for is dated by ``info.modified`` (the suggestion is not younger than that), and one with neither by the
    earliest date there is (D411)."""
    when = when_made(change_times, info.modified if info else None)
    by_block = open_replacements(model, track=track_suggestions)
    ids = _ids(set())
    root = etree.Element(
        _q("office", "document-content"), nsmap={prefix: uri for prefix, uri in NS.items() if prefix != "xml"}
    )
    root.set(_q("office", "version"), VERSION)
    for name in ("scripts", "font-face-decls", "automatic-styles"):
        etree.SubElement(root, _q("office", name))
    text = etree.SubElement(etree.SubElement(root, _q("office", "body")), _q("office", "text"))
    regions: list[etree._Element] = []
    for block in model.blocks:
        paragraph, found = _new_paragraph(block.style, block.text, by_block.get(block.id, []), ids, when)
        text.append(paragraph)
        regions += found
    if regions:
        tracked = _element("text", "tracked-changes", track_changes="false")
        tracked.extend(regions)
        text.insert(0, tracked)
    content = _DECLARATION + etree.tostring(root, encoding="unicode")
    return new_package("text", content.encode(), _styles_part(), meta=new_meta(info or DocumentInfo()))


def odt_export_losses(model: TextModel, *, track_suggestions: bool = True) -> tuple[Loss, ...]:
    """What :func:`text_to_odt` cannot put into the file for ``model``, each as a code with how many: a ``"style"``
    (named by its id) that is written as body text, ``"authorship"`` (who wrote which run of a block: an odt does not
    keep it), a ``"remark"`` (nothing to track), a ``"suggestion"`` that is not written because tracking is off and
    a ``"suggestion-anchor"`` that no longer matches its text."""
    losses = LossLog()
    for block in model.blocks:
        if block.style not in (*_ODF_NAME, DEFAULT_STYLE):
            losses.add("style", block.style)
    authored = sum(1 for block in model.blocks if any(run.author is not None for run in block.runs))
    if authored:
        losses.add("authorship", count=authored)
    open_ones = [s for s in model.suggestions.values() if s.state == "open"]
    remarks = sum(1 for s in open_ones if s.replacement is None)
    if remarks:
        losses.add("remark", count=remarks)
    if not track_suggestions:
        if len(open_ones) > remarks:
            losses.add("suggestion", count=len(open_ones) - remarks)
        return losses.result()
    blocks = {block.id: block for block in model.blocks}
    skipped = 0
    for block_id, suggestions in open_replacements(model).items():
        owner = blocks.get(block_id)
        skipped += _plan(owner.text, suggestions)[2] if owner else len(suggestions)
    if skipped:
        losses.add("suggestion-anchor", count=skipped)
    return losses.result()


# -- edit and re-export ----------------------------------------------------------------------------------------------
class _Patch:
    """One run of :func:`apply_edits_to_odt`: the original's parts, what is to change and the edits recorded so far."""

    def __init__(
        self,
        original: bytes,
        baseline: TextModel,
        current: TextModel,
        *,
        track: bool,
        losses: LossLog | None,
        info: DocumentInfo | None,
        when: WhenMade,
    ) -> None:
        self.original = original
        self.info = info
        self.when = when
        self.parts = _read(original)
        self.part = XmlPart(self.parts["content.xml"])
        self.body = _text_body(self.part.root)
        self.styles = XmlPart(self.parts["styles.xml"]) if "styles.xml" in self.parts else None
        self.current = current
        self.losses = losses
        self.by_block = open_replacements(current, track=track)
        self.ids = _ids({r.get(_q("text", "id")) or "" for r in self.part.root.iter(_q("text", "changed-region"))})
        roots = [self.part.root, *([self.styles.root] if self.styles else [])]
        self.defined = set(_paragraph_styles(*roots))
        self.missing: list[str] = []  # styles the file lacks, that the edits need
        self.regions: list[etree._Element] = []  # tracked changes to add
        self.appended: list[etree._Element] = []  # paragraphs that go at the end of the text
        self.changed = False
        paragraphs = _scan(self.body).paragraphs
        # A text with no paragraph at all still reads as a model with one empty block (that is what a new model is),
        # which is no paragraph of the file: nothing to patch, and if it is still empty there is nothing to add either.
        blank = [] if paragraphs else [b.id for b in baseline.blocks if not b.text and b.style == DEFAULT_STYLE][:1]
        self.blank = set(blank)
        held = [block for block in baseline.blocks if block.id not in self.blank]
        if len(paragraphs) != len(held):
            raise UnsupportedEdit("the baseline is not the text this file holds")
        self.held = held
        self.paragraphs = paragraphs
        self.element_of = {block.id: element for block, element in zip(held, paragraphs, strict=True)}
        self.before = {block.id: block for block in held}
        kept = [block.id for block in current.blocks if block.id in self.before]
        if kept != [block.id for block in held if block.id in set(kept)]:
            raise UnsupportedEdit("blocks cannot be moved relative to each other in the file")

    def run(self) -> bytes:
        self._remove_dropped()
        self._patch_current()
        self._put_in_new_markup()
        if not self.changed:
            return self.original
        self.parts["content.xml"] = self.part.result()
        self._add_missing_styles()
        if self.info is not None:
            update_package_meta(self.parts, self.info)
        return write_parts(self.parts)

    def _style_name(self, style_id: str) -> str:
        """The name a block of ``style_id`` is written with, noting a style the file must be given."""
        name = _ODF_NAME.get(style_id, _STANDARD)
        if style_id != DEFAULT_STYLE and style_id not in _ODF_NAME and self.losses is not None:
            self.losses.add("style", style_id)
        if name not in self.defined and name not in self.missing:
            self.missing.append(name)
        return name

    def _remove_dropped(self) -> None:
        kept = {block.id for block in self.current.blocks}
        for block in self.held:
            if block.id in kept:
                continue
            element = self.element_of[block.id]
            if self.losses is not None:
                for kind in hidden_content(element):
                    self.losses.add(f"removed-{kind}")
            self.part.remove(element)
            self.changed = True

    def _patch_current(self) -> None:
        anchor: etree._Element | None = None  # the paragraph of the file that the block before this one is
        for block in self.current.blocks:
            suggestions = self.by_block.get(block.id, [])
            if block.id in self.blank and not block.text and block.style == DEFAULT_STYLE and not suggestions:
                continue
            if block.id in self.before:
                anchor = self.element_of[block.id]
                self._edit(block, anchor, suggestions)
            else:
                self._add(block, anchor, suggestions)

    def _add(self, block: Block, anchor: etree._Element | None, suggestions: list[Suggestion]) -> None:
        """A new block goes next to the paragraph before it, in whatever holds that (a list item, a section), or before
        the first paragraph, or at the end of a text that has none."""
        paragraph, found = _new_paragraph(block.style, block.text, suggestions, self.ids, self.when)
        self._style_name(block.style)
        self.regions += found
        if anchor is not None:
            self.part.insert_after(anchor, paragraph)
        elif self.paragraphs:
            self.part.insert_before(self.paragraphs[0], paragraph)
        else:
            self.appended.append(paragraph)
        self.changed = True

    def _edit(self, block: Block, element: etree._Element, suggestions: list[Suggestion]) -> None:
        old = self.before[block.id]
        if old.text == block.text and old.style == block.style and not suggestions:
            return
        edited = copy.deepcopy(element)
        text, changes, _ = _plan(block.text, suggestions, self.when)
        set_text(edited, text)
        name = edited.get(_STYLE_NAME) or _STANDARD
        if old.style != block.style:
            name = self._restyle(edited, block.style)
        self.regions += _write_changes(edited, changes, self.ids, name)
        self.part.replace(element, edited)
        self.changed = True

    def _restyle(self, paragraph: etree._Element, style_id: str) -> str:
        """Make ``paragraph`` (a copy) a paragraph or a heading of the style ``style_id``; its name."""
        name = self._style_name(style_id)
        level = _LEVEL.get(style_id)
        paragraph.tag = _H if level else _P
        paragraph.set(_STYLE_NAME, name)
        if level:
            paragraph.set(_OUTLINE, str(level))
        elif _OUTLINE in paragraph.attrib:
            del paragraph.attrib[_OUTLINE]
        return name

    def _put_in_new_markup(self) -> None:
        """The tracked changes, and the paragraphs that have no neighbour to go next to, into the text. Where the text
        is one empty tag, a single edit opens it, so everything that goes in goes in together."""
        tracked = self.body.find("text:tracked-changes", NS)
        if self.regions and tracked is not None:
            self.part.insert_into(tracked, *self.regions)
            self.regions = []
        container = None
        if self.regions:
            container = _element("text", "tracked-changes", track_changes="false")
            container.extend(self.regions)
        first = [container] if container is not None else []
        if len(self.body) == 0:
            if first or self.appended:
                self.part.insert_into(self.body, *first, *self.appended)
            return
        if container is not None:
            self.part.insert_into(self.body, container, at_start=True)
        if self.appended:
            self.part.insert_into(self.body, *self.appended)

    def _add_missing_styles(self) -> None:
        if not self.missing:
            return
        styles = self.styles.root.find("office:styles", NS) if self.styles is not None else None
        if self.styles is None or styles is None:
            raise OdfError("this file has no styles to add the style of a block to")
        self.styles.insert_into(styles, "".join(_STYLE_XML[name] for name in self.missing).encode())
        self.parts["styles.xml"] = self.styles.result()


def apply_edits_to_odt(
    original_bytes: bytes,
    baseline: TextModel,
    current: TextModel,
    *,
    track_suggestions: bool = True,
    losses: LossLog | None = None,
    info: DocumentInfo | None = None,
    change_times: Mapping[str, str] | None = None,
) -> bytes:
    """Re-export ``current`` to odt by patching what changed since ``baseline`` (the model as :func:`odt_to_text` read
    it from ``original_bytes``) onto those same bytes -- so a table, a picture, a footnote, a style, anything the text
    app does not model, is still in the file, and every byte of ``content.xml`` outside the paragraphs that were
    edited is the original's. Every other part of the package is exactly as it was. With nothing changed the result *is*
    ``original_bytes``.

    What it patches: the text of a block (edited in place, so the spans, links, bookmarks and notes inside the
    paragraph stay where they were), its style (a paragraph and a heading change into each other, and a style the
    file does not have yet is added to it), blocks that were added or removed (``losses`` gets a ``removed-...`` entry
    for each note, frame or comment that went with a removed block), and open suggestions, as tracked changes.

    ``info`` and ``change_times`` are as for :func:`text_to_odt`. With ``info``, a file that was changed also has its
    ``meta.xml`` brought up to date (:func:`claudia_odf_io.update_package_meta`: when and by whom it was saved, one more
    edit counted; the rest of it as it was); a file that was not changed is not touched, and without ``info`` the
    metadata is left alone (D411).

    Raises :class:`UnsupportedEdit` for what cannot be patched: a baseline that is not what the file holds, and blocks
    moved relative to each other (a move would have to carry what is inside a paragraph, which it does not know)."""
    when = when_made(change_times, info.modified if info else None)
    return _Patch(original_bytes, baseline, current, track=track_suggestions, losses=losses, info=info, when=when).run()
