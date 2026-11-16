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
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from itertools import count
from typing import cast
from zipfile import BadZipFile

from lxml import etree

from claudia_composes import BUILTIN_STYLES, DEFAULT_STYLE, Block, BlockAnchor, Run, Suggestion, TextModel
from claudia_core import SHAPE_LABEL_STYLE, Rasterise, VisualObject, primitive
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
    default_style_xml,
    frames_of,
    hidden_content,
    insert_elements,
    new_meta,
    new_package,
    read_text,
    set_text,
    update_manifest,
    update_package_meta,
    xml_safe,
)
from claudia_opc_io import read_parts, write_parts

from ._boxes import box_losses, boxes_of, is_written, look_of
from ._odt_boxes import BoxPlan, BoxStyles, BoxWriter, FileBox, file_boxes, graphic_style_names
from ._odt_lists import LIST, ListFlow, ListNames, can_rebuild, read_lists
from ._odt_pictures import (
    PICTURE_STYLE,
    PICTURE_STYLE_XML,
    FilePicture,
    PicturePlan,
    PictureWriter,
    file_pictures,
    frames_not_pictures,
    graphic_styles,
    unheld_pictures,
)
from ._odt_setup import (
    FOOTER_STYLE,
    FOOTER_STYLE_XML,
    master_page_xml,
    page_layout_xml,
    patch_language,
    patch_page,
    read_setup,
)
from ._odt_styles import StyleNames, style_xml
from ._pictures import picture_losses, pictures_of
from ._suggestions import WhenMade, open_replacements, when_made
from ._unwritten import ODT_WRITTEN, text_unwritten_changes
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
_TABLE = _q("table", "table")

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


def _names_in(root: etree._Element) -> list[str]:
    """Every name a style or an ``xml:id`` of a part has taken."""
    found = [
        name
        for element in root.iter(_q("style", "style"), _q("text", "list-style"))
        if (name := element.get(_q("style", "name")))
    ]
    ids = root.xpath("//@xml:id")
    return found + [value for value in ids if isinstance(value, str)] if isinstance(ids, list) else found


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


#: The model's styles of words by the name an odt shows for them, for a text box or a shape of a file.
_WORDS_STYLE = {style.name: style.id for style in BUILTIN_STYLES if style.kind == "paragraph"}


def _words_style(parents: dict[str, str | None]) -> Callable[[etree._Element, str | None], str]:
    """The style of the model the paragraph in a text box or a shape (``shape``: the one it is, else ``None``) has: the
    one its style is based on, else the one of that name, else the style of the words of the kind of box."""

    def of(paragraph: etree._Element, shape: str | None) -> str:
        found = _style_of(paragraph, parents, None)
        named = _WORDS_STYLE.get(decode_style_name(paragraph.get(_STYLE_NAME) or ""))
        if found != DEFAULT_STYLE:
            return found
        return named or (DEFAULT_STYLE if shape is None else SHAPE_LABEL_STYLE)

    return of


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


def _lists_of(parts: dict[str, bytes], body: etree._Element, scan: _Scan):  # noqa: ANN202
    """The lists of a file and the items among its paragraphs (:func:`claudia_composes_io._odt_lists.read_lists`)."""
    content = body.getroottree().getroot()
    styles = etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else content
    return read_lists(scan.paragraphs, (content, styles))


def odt_to_text(odt_bytes: bytes) -> TextModel:
    """``odt_bytes`` as a :class:`~claudia_composes.TextModel`: one block per paragraph of the flow, in order,
    called ``b1``, ``b2``... by its place. Title, Heading 1, Heading 2 and Quotations (or a style based on one) map to
    the styles of the text app and anything else is body text. The first paragraph of every item of a list is an item
    of that list (the scheme, start and name of the list from its list style, ``_odt_lists``), at the level of its
    place in the nest. A picture (a ``draw:frame`` with an image in it) that the model shows as it is -- an image the
    app decodes, not cropped, in its own proportions -- is an image object hanging from the character it stands at,
    with its description (D464). What the model does not show is in :func:`odt_import_losses`. Raises
    :class:`~claudia_odf_io.OdfError` for a file that is not an odt."""
    parts, body, scan, parents = _document(odt_bytes)
    lists = _lists_of(parts, body, scan)
    setup = read_setup(etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else None)
    blocks = []
    for number, paragraph in enumerate(scan.paragraphs, start=1):
        text = read_text(paragraph)
        runs = (Run(len(text), None),) if text else ()
        blocks.append(Block(f"b{number}", _style_of(paragraph, parents, None), text, runs, lists.items.get(paragraph)))
    model = TextModel(blocks or None, page=setup.page, language=setup.language, lists=lists.book if blocks else None)
    root = body.getroottree().getroot()
    graphics = graphic_styles(root, etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else None)
    floating: list[tuple[int, int, int, FilePicture | FileBox]] = [
        (each.block, each.offset, 0, each) for each in file_pictures(scan.paragraphs, graphics, parts)
    ]
    floating += [
        (each.block, each.offset, 1, each) for each in file_boxes(scan.paragraphs, graphics, _words_style(parents))
    ]
    for _, _, _, each in sorted(floating, key=lambda found: found[:3]):
        if isinstance(each, FileBox):
            if each.body.shape is not None and each.body.shape not in model.shapes:
                model.define_shape(primitive(each.body.shape))
        elif each.asset.id not in model.images:
            model.define_image(each.asset)
        model.insert_object(VisualObject(each.body, BlockAnchor(f"b{each.block + 1}", each.offset)))
    return model


def odt_import_losses(odt_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`odt_to_text` does not show of the file, each as a code (``"table"``, ``"footnote"``,
    ``"formatting"``, ``"list-look"`` for lists drawn otherwise than the model draws them, ``"page"`` for a page the
    model cannot hold, ``"picture"`` for one it does not show as it is...) with how many there are, in the order they
    come. None of it is lost from the *file*: an edit that is exported with :func:`apply_edits_to_odt` keeps all of
    it."""
    parts, body, scan, parents = _document(odt_bytes)
    reading = _lists_of(parts, body, scan)
    setup = read_setup(etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else None)
    losses = LossLog()
    hidden: dict[str, int] = {}
    formatting = links = 0
    for paragraph in scan.paragraphs:
        _style_of(paragraph, parents, losses)
        for kind in hidden_content(paragraph):
            hidden[kind] = hidden.get(kind, 0) + 1
        formatting += sum(1 for span in paragraph.iter(_q("text", "span")) if span.get(_STYLE_NAME))
        links += sum(1 for _ in paragraph.iter(_q("text", "a")))
    graphics = graphic_styles(
        body.getroottree().getroot(), etree.fromstring(parts["styles.xml"]) if "styles.xml" in parts else None
    )
    held = file_pictures(scan.paragraphs, graphics, parts)
    unheld = unheld_pictures(scan.paragraphs, held, graphics)
    shown_as_frames = sum(1 for paragraph in scan.paragraphs for frame in frames_of(paragraph))
    boxes = file_boxes(scan.paragraphs, graphics, _words_style(parents))
    plain = shown_as_frames - sum(frames_not_pictures(paragraph) for paragraph in scan.paragraphs)
    plain += len(boxes)  # (the boxes are shown as they are, they are no frame of their own)
    if "frame" in hidden:  # (the pictures are shown or are a picture of their own, not a frame)
        hidden["frame"] -= plain
        if hidden["frame"] <= 0:
            del hidden["frame"]
    if unheld:
        hidden["picture"] = unheld
    for code, number in (
        ("table", scan.tables),
        ("list-look", reading.odd_looks),
        ("list-depth", reading.too_deep),
        ("page", int(setup.odd_page)),
        ("index", scan.indexes),
        ("frame", scan.frames),
        ("look", sum(1 for box in boxes if not box.look.matches(look_of(TextModel(None), box.body)))),
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


def _moved(offset: int, text: str, suggestions: list[Suggestion]) -> int:
    """Where the character ``offset`` of a block's own ``text`` is in the text of its paragraph, in which the
    replacements of ``suggestions`` stand for what they replace (what :func:`_plan` writes); one inside what is
    replaced is before its replacement."""
    shift, position = 0, 0
    for suggestion in suggestions:
        start, end = suggestion.anchor.start, suggestion.anchor.end
        if start < position or end > len(text):
            continue
        if offset <= start:
            break
        if offset < end:
            return start + shift
        shift += len(xml_safe(suggestion.replacement or "")) - (end - start)
        position = end
    return offset + shift


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
    style_id: str, text: str, suggestions: list[Suggestion], ids: Iterator[str], when: WhenMade, names: StyleNames
) -> tuple[etree._Element, list[etree._Element]]:
    """A paragraph element for a block, and the tracked-change regions of its suggestions."""
    name = names.of(style_id)
    level = _LEVEL.get(style_id)
    paragraph = etree.Element(_H if level else _P, nsmap={"text": NS["text"]})
    paragraph.set(_STYLE_NAME, name)
    if level:
        paragraph.set(_OUTLINE, str(level))
    body, changes, _ = _plan(text, suggestions, when)
    set_text(paragraph, body)
    return paragraph, _write_changes(paragraph, changes, ids, name)


# -- export ----------------------------------------------------------------------------------------------------------
def _style_definitions(model: TextModel, names: StyleNames) -> tuple[list[bytes], list[tuple[str, str]]]:
    """The styles of the model as odt styles (the built-in ones first, so that every file has them), and what of them a
    file cannot say, as ``(style id, property)``."""
    colours = model.palette.colours()
    found: list[bytes] = []
    unsaid: list[tuple[str, str]] = []
    for style in model.styles:
        if style.kind != "paragraph":
            continue
        xml, lost = style_xml(model.styles, style, names, colours)
        found.append(xml)
        unsaid += [(style.id, prop) for prop in lost]
    return found, unsaid


def _styles_part(model: TextModel, names: StyleNames) -> bytes:
    """``styles.xml`` of a new file: the styles of the text, the language of the text and its page."""
    definitions = b"".join(_style_definitions(model, names)[0]).decode()
    footer = FOOTER_STYLE_XML if model.page.page_numbers else ""
    styles = default_style_xml(model.language) + definitions + footer
    return (
        f'{_DECLARATION}<office:document-styles {_NS_DECLS} office:version="{VERSION}">'
        f"<office:styles>{styles}</office:styles>"
        f"<office:automatic-styles>{page_layout_xml(model.page)}</office:automatic-styles>"
        f"<office:master-styles>{master_page_xml(model.page)}</office:master-styles>"
        "</office:document-styles>"
    ).encode()


def text_to_odt(
    model: TextModel,
    *,
    track_suggestions: bool = True,
    info: DocumentInfo | None = None,
    change_times: Mapping[str, str] | None = None,
    rasterise: Rasterise | None = None,
) -> bytes:
    """``model`` as odt bytes: one paragraph (or heading) per block, the built-in styles written as the styles of the
    same name, and an item of a list as the item of a ``text:list`` (nested for its level) with a list style that has
    the scheme, start and name of its list; a list that goes on after a paragraph is written as a list that continues
    the one before. When ``track_suggestions`` (the default), every open suggestion that proposes a replacement is
    written as a tracked change a reviewer can accept or reject in any OpenDocument program; a remark has no text to
    track and is left out, as is one that is resolved or withdrawn. Anything else not in the file is in
    :func:`odt_export_losses`.

    ``info`` is what the file says about the document in ``meta.xml`` (title, who made it and when, who saved it last
    and when). ``change_times`` has when each suggestion was made, by id, and dates its tracked change; one it has no
    time for is dated by ``info.modified`` (the suggestion is not younger than that), and one with neither by the
    earliest date there is (D411). A picture floating over the text (an image, a rendered text container) is a frame in
    the paragraph it hangs from, at its character, with its description; a rendered container is drawn as a PNG by
    ``rasterise`` when there is one (D464)."""
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
    styles = StyleNames(model.styles)
    names = ListNames(model.lists)
    flow = ListFlow(text, lambda list_id, element: names.start(list_id, element))
    regions: list[etree._Element] = []
    pictures = PictureWriter(rasterise)
    box_styles = BoxStyles()
    boxes = BoxWriter(
        model, box_styles, lambda style_id, words: _new_paragraph(style_id, words, [], ids, when, styles)[0]
    )
    for block in model.blocks:
        paragraph, found = _new_paragraph(block.style, block.text, by_block.get(block.id, []), ids, when, styles)
        _add_pictures(paragraph, model, block, by_block.get(block.id, []), pictures)
        _add_boxes(paragraph, model, block, by_block.get(block.id, []), boxes)
        flow.add(paragraph, block.item)
        regions += found
    automatic = root.find("office:automatic-styles", NS)
    if automatic is not None:
        automatic.extend(etree.fromstring(style) for style in names.new_styles)
        automatic.extend(etree.fromstring(style) for style in box_styles.new)
        if pictures.parts:
            automatic.append(etree.fromstring(PICTURE_STYLE_XML))
    if regions:
        tracked = _element("text", "tracked-changes", track_changes="false")
        tracked.extend(regions)
        text.insert(0, tracked)
    content = _DECLARATION + etree.tostring(root, encoding="unicode")
    return new_package(
        "text",
        content.encode(),
        _styles_part(model, styles),
        meta=new_meta(info or DocumentInfo()),
        extra={name: (data, pictures.media_types[name]) for name, data in pictures.parts.items()},
    )


def _add_pictures(
    paragraph: etree._Element, model: TextModel, block: Block, suggestions: list[Suggestion], writer: PictureWriter
) -> None:
    """Put the frames of the pictures that hang from ``block`` into its ``paragraph``, each at its character."""
    marks = [
        (_moved(obj.anchor.offset, block.text, suggestions), writer.frame(obj, asset))
        for obj, asset in pictures_of(model, block.id)
    ]
    insert_elements(paragraph, marks)


def _add_boxes(
    paragraph: etree._Element, model: TextModel, block: Block, suggestions: list[Suggestion], writer: BoxWriter
) -> None:
    """Put the text boxes and shapes that hang from ``block`` into its ``paragraph``, each at its character."""
    insert_elements(
        paragraph,
        [
            (_moved(obj.anchor.offset, block.text, suggestions), writer.element(obj))
            for obj in boxes_of(model, block.id)
        ],
    )


def odt_export_losses(
    model: TextModel, *, track_suggestions: bool = True, rasterised: bool = False
) -> tuple[Loss, ...]:
    """What :func:`text_to_odt` cannot put into the file for ``model``, each as a code with how many: a ``"style"``
    (named by its id) that is written as body text, ``"authorship"`` (who wrote which run of a block: an odt does not
    keep it), a ``"remark"`` (nothing to track), a ``"suggestion"`` that is not written because tracking is off and
    a ``"suggestion-anchor"`` that no longer matches its text, ``"decorative"`` (a picture marked as decoration: ODF 1.3
    has no attribute for it, so a reader of the file sees a picture nobody described), ``"rendering-pending"`` (a
    rendered text container nothing has been drawn for yet: left out), ``"svg-picture"`` (a rendered container written
    as the SVG itself because nothing could draw it as a PNG, ``rasterised``), and what :func:`odt_unwritten_changes`
    says of a fresh file."""
    losses = LossLog()
    names = StyleNames(model.styles)
    for block in model.blocks:
        if block.style not in names:
            losses.add("style", block.style)
    for style_id, prop in _style_definitions(model, names)[1]:
        losses.add("style-property", f"{style_id}: {prop}")
    authored = sum(1 for block in model.blocks if any(run.author is not None for run in block.runs))
    if authored:
        losses.add("authorship", count=authored)
    open_ones = [s for s in model.suggestions.values() if s.state == "open"]
    remarks = sum(1 for s in open_ones if s.replacement is None)
    if remarks:
        losses.add("remark", count=remarks)
    decorative = sum(
        1
        for obj in model.objects.values()
        if (obj.body.kind in ("image", "rendered") or is_written(obj)) and obj.body.decorative
    )
    if decorative:
        losses.add("decorative", count=decorative)
    picture_losses(model, losses, vector_loss=None if rasterised else "svg-picture", only_rendered=True)
    box_losses(model, losses)
    if not track_suggestions:
        if len(open_ones) > remarks:
            losses.add("suggestion", count=len(open_ones) - remarks)
        return (*losses.result(), *odt_unwritten_changes(model))
    blocks = {block.id: block for block in model.blocks}
    skipped = 0
    for block_id, suggestions in open_replacements(model).items():
        owner = blocks.get(block_id)
        skipped += _plan(owner.text, suggestions)[2] if owner else len(suggestions)
    if skipped:
        losses.add("suggestion-anchor", count=skipped)
    return (*losses.result(), *odt_unwritten_changes(model))


def odt_unwritten_changes(model: TextModel, baseline: TextModel | None = None) -> tuple[Loss, ...]:
    """What changed in ``model`` that the odt converters do not write: each a ``"not-written"`` code with the facet
    (``"page"``, ``"language"``, ``"lists"``...) and how many entries of it differ from ``baseline`` -- the model the
    original file was read as, for an edit-and-reexport -- or from an empty text, for a fresh file (``None``)."""
    return text_unwritten_changes(model, baseline, written=ODT_WRITTEN)


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
        rasterise: Rasterise | None,
    ) -> None:
        self.original = original
        self.info = info
        self.when = when
        self.parts = _read(original)
        self.part = XmlPart(self.parts["content.xml"])
        self.body = _text_body(self.part.root)
        self.styles = XmlPart(self.parts["styles.xml"]) if "styles.xml" in self.parts else None
        self.baseline = baseline
        self.current = current
        self.losses = losses
        self.by_block = open_replacements(current, track=track)
        self.ids = _ids({r.get(_q("text", "id")) or "" for r in self.part.root.iter(_q("text", "changed-region"))})
        roots = [self.part.root, *([self.styles.root] if self.styles else [])]
        self.defined = set(_paragraph_styles(*roots))
        own = {StyleNames(baseline.styles).of(style.id) for style in baseline.styles if style.kind == "paragraph"}
        self.style_names = StyleNames(current.styles, self.defined - own)  # (a style the file has by our name is ours)
        self.missing: dict[str, bytes] = {}  # styles the file lacks, that the edits need, by name
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
        graphics = graphic_styles(*roots)
        self.has_picture_style = PICTURE_STYLE in graphics
        self.pictures = PicturePlan(
            file_pictures(paragraphs, graphics, self.parts),
            [block.id for block in held],
            baseline,
            current,
            rasterise,
            set(self.parts),
            losses,
        )
        self.box_styles = BoxStyles(graphic_style_names(*roots))
        self.boxes = BoxPlan(
            file_boxes(paragraphs, graphics, _words_style(_paragraph_styles(*roots))),
            [block.id for block in held],
            baseline,
            current,
            BoxWriter(current, self.box_styles, self._words_paragraph),
            losses,
        )
        self.before = {block.id: block for block in held}
        self.reading = read_lists(paragraphs, [self.part.root, self.styles.root if self.styles else self.part.root])
        self.top = {block.id: self.reading.container[self.element_of[block.id]] for block in held}
        changed = [
            list_id
            for list_id in self.reading.book.ids()
            if list_id in current.lists and current.lists.get(list_id) != self.reading.book.get(list_id)
        ]
        taken = {name for root in roots for name in _names_in(root)}
        self.names = ListNames(current.lists, taken, self.reading.style_of, changed)
        self.changed_lists = set(changed)
        self.passed: set[etree._Element] = set()
        kept = [block.id for block in current.blocks if block.id in self.before]
        if kept != [block.id for block in held if block.id in set(kept)]:
            raise UnsupportedEdit("blocks cannot be moved relative to each other in the file")

    def run(self) -> bytes:
        if self.losses is not None:  # (what a rendered container is that nothing has been drawn for)
            picture_losses(self.current, self.losses, only_rendered=True)
        self.plan = self._plan()
        self._remove_dropped()
        self._patch_current()
        self._put_in_new_markup()
        self._finish_lists()
        setup_changed = self._patch_setup()
        setup_changed = self._patch_style_definitions() or setup_changed
        if not self.changed and not setup_changed:
            return self.original
        if self.changed:
            self.parts["content.xml"] = self.part.result()
            self._settle_pictures_in_package()
        self._add_missing_styles(setup_changed)
        if self.info is not None:
            update_package_meta(self.parts, self.info)
        return write_parts(self.parts)

    def _words_paragraph(self, style_id: str, words: str) -> etree._Element:
        """The paragraph of the words of a box, in the style of the model (noting the style the file must be given)."""
        self._style_name(style_id)
        return _new_paragraph(style_id, words, [], self.ids, self.when, self.style_names)[0]

    def _settle_pictures_in_package(self) -> None:
        """The images of the new frames into the package and its manifest; those of frames that went out of it, when no
        frame left shows them (and no name of the package starts with theirs: the manifest drops by prefix)."""
        plan = self.pictures
        hrefs = cast(list[str], etree.fromstring(self.parts["content.xml"]).xpath("//@xlink:href", namespaces=NS))
        still = {href.removeprefix("./") for href in hrefs}
        styles = self.parts.get("styles.xml", b"")
        orphans = {
            name
            for name in plan.removed
            if name in self.parts
            and name not in still
            and name.encode() not in styles
            and not any(other != name and other.startswith(name) for other in self.parts)
        }
        for name in orphans:
            del self.parts[name]
        if plan.writer.parts or orphans:
            self.parts.update(plan.writer.parts)
            update_manifest(self.parts, add=plan.writer.media_types, remove=tuple(orphans))

    def _style_name(self, style_id: str) -> str:
        """The name a block of ``style_id`` is written with, noting a style the file must be given."""
        name = self.style_names.of(style_id)
        if style_id not in self.style_names and self.losses is not None:
            self.losses.add("style", style_id)
        if name not in self.defined and name not in self.missing:
            self.missing[name] = self._definition_of(style_id)
        return name

    def _definition_of(self, style_id: str) -> bytes:
        """The style ``style_id`` of the text as an odt style; the style of body text for one the text does not have."""
        book = self.current.styles
        found = style_id if style_id in self.style_names else DEFAULT_STYLE
        return style_xml(book, book.get(found), self.style_names, self.current.palette.colours())[0]

    def _remove_dropped(self) -> None:
        kept = {block.id for block in self.current.blocks}
        for block in self.held:
            if block.id in kept:
                continue
            element = self.element_of[block.id]
            if self.losses is not None:
                for kind in hidden_content(element):
                    self.losses.add(f"removed-{kind}")
            if self.top[block.id] not in self.dirty:
                self.part.remove(element)
            self.changed = True  # (else the list it was in is written again, without it)
        in_use = {top for kind, top in self.plan if kind == "region"}
        for top in self.dirty - in_use:  # a list none of whose blocks is left
            self.part.remove(top)

    # -- what goes where: the structure of lists --------------------------------------------------------------------
    def _dirty_containers(self) -> set[etree._Element]:
        """The lists of the file that are written again: one with an item that is no longer one, or is one of another
        list, with a block removed from it, with a new block among its blocks or right after its last item."""
        blocks = self.current.blocks
        kept = {block.id for block in blocks}
        dirty: set[etree._Element] = set()
        where: dict[etree._Element, list[int]] = {}
        for number, block in enumerate(blocks):
            if block.id in self.before:
                where.setdefault(self.top[block.id], []).append(number)
                if self.before[block.id].item != block.item:
                    dirty.add(self.top[block.id])
        dirty |= {self.top[b.id] for b in self.held if b.id not in kept and self.top[b.id].tag not in (_P, _H)}
        for top, numbers in where.items():
            if top.tag in (_P, _H):
                continue
            first, last = numbers[0], numbers[-1]
            new_inside = any(blocks[n].id not in self.before for n in range(first, last + 1))
            after = blocks[last + 1] if last + 1 < len(blocks) else None
            if new_inside or (after is not None and after.id not in self.before and after.item):
                dirty.add(top)
        for top in dirty:
            if not can_rebuild(top):
                raise UnsupportedEdit("a list with more in it than items and paragraphs cannot be changed in structure")
        return dirty

    def _plan(self) -> list[tuple[str, etree._Element | int | None]]:
        """What each current block is: ``"keep"`` (a paragraph of the file whose place in its list did not change; with
        its top-level element), ``"region"`` (one of the blocks of a list, or paragraph, that is written again, with
        that element), ``"run"`` (a new item, with the number of its run of items) or ``"plain"`` (a new paragraph)."""
        blocks = self.current.blocks
        dirty = self._dirty_containers()
        self.dirty = dirty
        plan: list[tuple[str, etree._Element | int | None]] = []
        region: etree._Element | None = None
        runs = 0
        for block in blocks:
            if block.id in self.before:
                top = self.top[block.id]
                region = top if top in dirty else None
                plan.append(("region" if region is not None else "keep", top))
            elif region is not None:
                plan.append(("region", region))
            elif block.item is not None:
                if not plan or plan[-1][0] != "run":
                    runs += 1
                plan.append(("run", runs))
            else:
                plan.append(("plain", None))
        return plan

    def _paragraph_of(self, block: Block, suggestions: list[Suggestion]) -> etree._Element:
        """The paragraph of a block that is written again: its element in the file (edited, in a copy) or a new one."""
        if block.id in self.before:
            element = self.element_of[block.id]
            edited = self._edited(block, element, suggestions)
            found = copy.deepcopy(element) if edited is None else edited
        else:
            found, regions = _new_paragraph(block.style, block.text, suggestions, self.ids, self.when, self.style_names)
            self._style_name(block.style)
            self.regions += regions
            self._hang_pictures(found, block, suggestions)
        found.tail = None
        return found

    def _written(self, blocks: list[Block], inherit: etree._Element | None = None) -> list[etree._Element]:
        """The top-level elements that hold ``blocks`` as the text says: lists for the items, the rest as paragraphs."""
        holder = etree.Element("holder")
        inheriting = [inherit]

        def start(list_id: str, element: etree._Element) -> None:
            same = inheriting[0] is not None and self.reading.list_of.get(inheriting[0]) == list_id
            self.names.start(list_id, element, inheriting[0] if same else None)
            if same:
                inheriting[0] = None

        flow = ListFlow(holder, start)
        for block in blocks:
            flow.add(self._paragraph_of(block, self.by_block.get(block.id, [])), block.item)
        return list(holder)

    def _place(self, elements: list[etree._Element], after: etree._Element | None) -> None:
        """New top-level elements, next to the one before them, or before the first of the text, or in an empty one."""
        for element in elements:
            if after is not None:
                self.part.insert_after(after, element)
            elif self.paragraphs:
                assert self.first_top is not None  # a text with paragraphs has a first one (set in _patch_current)
                self.part.insert_before(self.first_top, element)
            else:
                self.appended.append(element)
        self.changed = True

    def _patch_current(self) -> None:
        plan = self.plan
        blocks = self.current.blocks
        self.first_top = self.top[self.held[0].id] if self.held else None
        anchor: etree._Element | None = None  # the top-level element that the block before this one is in
        number = 0
        while number < len(blocks):
            block = blocks[number]
            kind, payload = plan[number]
            suggestions = self.by_block.get(block.id, [])
            if block.id in self.blank and not block.text and block.style == DEFAULT_STYLE and not suggestions:
                number += 1
                continue
            end = number + 1
            while kind in ("region", "run") and end < len(blocks) and plan[end] == plan[number]:
                end += 1
            if kind == "keep":
                assert isinstance(payload, etree._Element)
                anchor = payload
                self._keep(block, payload, suggestions)
            elif kind == "region":
                assert isinstance(payload, etree._Element)
                elements = self._written(blocks[number:end], payload)
                if elements:
                    self.part.replace(payload, *elements)
                else:
                    self.part.remove(payload)
                self.changed = True
                anchor = payload
            elif kind == "run":
                self._place(self._written(blocks[number:end]), anchor)
            else:
                paragraph, found = _new_paragraph(
                    block.style, block.text, suggestions, self.ids, self.when, self.style_names
                )
                self._style_name(block.style)
                self.regions += found
                self._hang_pictures(paragraph, block, suggestions)
                self._place([paragraph], anchor)
            number = end

    def _keep(self, block: Block, top: etree._Element, suggestions: list[Suggestion]) -> None:
        """A paragraph that stays where it is in its list: its words and style, and the style of its list."""
        self._edit(block, self.element_of[block.id], suggestions)
        if block.item is not None and top.tag == LIST and top not in self.passed:
            self.passed.add(top)
            list_id = block.item.list
            follows = self.names.passed(list_id, top)
            attributes = {}
            if list_id in self.changed_lists:
                attributes["text:style-name"] = self.names.style(list_id)
            if follows is not None and top.get(_q("text", "continue-list")) != follows:
                attributes["text:continue-list"] = follows
            if attributes:
                self.part.set_attributes(top, attributes)
                self.changed = True

    def _edited(self, block: Block, element: etree._Element, suggestions: list[Suggestion]) -> etree._Element | None:
        """A copy of the paragraph ``element`` with the words and the style the block has now; ``None`` if it has
        what the block has."""
        old = self.before[block.id]
        if (
            old.text == block.text
            and old.style == block.style
            and not suggestions
            and block.id not in self.pictures.touched
            and block.id not in self.boxes.touched
        ):
            return None
        edited = copy.deepcopy(element)
        text, changes, _ = _plan(block.text, suggestions, self.when)
        framed = self.pictures.has_any(block.id) or self.boxes.has_any(block.id)
        if framed:  # (the frames of the pictures and boxes are put back at the end, where the text says they hang)
            self.pictures.take_out(edited, element, block.id)
            self.boxes.take_out(edited, element, block.id)
        set_text(edited, text)
        name = edited.get(_STYLE_NAME) or _STANDARD
        if old.style != block.style:
            name = self._restyle(edited, block.style)
        self.regions += _write_changes(edited, changes, self.ids, name)
        if framed:
            self._hang_pictures(edited, block, suggestions)
        return edited

    def _hang_pictures(self, paragraph: etree._Element, block: Block, suggestions: list[Suggestion]) -> None:
        """The frames of the pictures that hang from ``block``, each at its character of ``paragraph``, as written."""
        where = lambda offset: _moved(offset, block.text, suggestions)  # noqa: E731
        self.pictures.hang(paragraph, block.id, where)
        self.boxes.hang(paragraph, block.id, where)

    def _edit(self, block: Block, element: etree._Element, suggestions: list[Suggestion]) -> None:
        edited = self._edited(block, element, suggestions)
        if edited is not None:
            self.part.replace(element, edited)
            self.changed = True

    def _finish_lists(self) -> None:
        """The list styles the text needs and the ``xml:id`` that the lists after a list of the file continue."""
        styles = [*self.names.new_styles, *self.box_styles.new]
        if self.pictures.written and not self.has_picture_style:
            styles.append(PICTURE_STYLE_XML.encode())
        if styles:
            automatic = self.part.root.find("office:automatic-styles", NS)
            if automatic is None:
                raise UnsupportedEdit("this file has no place for the style of a list or of a picture")
            self.part.insert_into(automatic, *styles)
            self.changed = True
        for element, xml_id in self.names.ids_to_add().items():
            self.part.set_attributes(element, {"xml:id": xml_id})
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

    def _patch_setup(self) -> bool:
        """The page and the language of the file, made what the text says where it changed; did it change them?"""
        before, after = self.baseline, self.current
        if before.page == after.page and before.language == after.language:
            return False
        if self.styles is None:
            raise UnsupportedEdit("this file has no styles.xml to say the page or the language in")
        changed = patch_page(self.styles, before.page, after.page)
        changed = patch_language(self.styles, before.language, after.language) or changed
        if after.page.page_numbers and not before.page.page_numbers and FOOTER_STYLE not in self.defined:
            self.missing[FOOTER_STYLE] = FOOTER_STYLE_XML.encode()
        return changed

    def _patch_style_definitions(self) -> bool:
        """The styles of the text whose definition changed since the baseline (a new style, another look, another
        colour in the palette it names), written into the file: over the file's style of that name, or as a new one."""
        before, after = self.baseline, self.current
        if (
            before.styles.ids() == after.styles.ids()
            and before.palette == after.palette
            and all(before.styles.get(i) == after.styles.get(i) for i in after.styles.ids())
        ):
            return False
        if self.styles is None:
            raise UnsupportedEdit("this file has no styles.xml to write the styles of the text in")
        before_names = StyleNames(before.styles, self.defined)  # (named as now: a name the file has is taken)
        colours_before, colours_after = before.palette.colours(), after.palette.colours()
        elements = {
            e.get(_q("style", "name")): e
            for e in self.styles.root.iterfind("office:styles/style:style", NS)
            if e.get(_q("style", "family")) == "paragraph"
        }
        changed = False
        for style in after.styles:
            if style.kind != "paragraph":
                continue
            now = style_xml(after.styles, style, self.style_names, colours_after)[0]
            if style.id in before.styles:
                was = style_xml(before.styles, before.styles.get(style.id), before_names, colours_before)[0]
                if was == now:
                    continue
            name = self.style_names.of(style.id)
            if style.id in before.styles and name in elements:  # a style the text had, in another look
                self.styles.replace(elements[name], now)
                changed = True
            elif name not in self.defined and name not in self.missing:
                self.missing[name] = now
        return changed

    def _add_missing_styles(self, setup_changed: bool = False) -> None:
        if self.missing:
            styles = self.styles.root.find("office:styles", NS) if self.styles is not None else None
            if self.styles is None or styles is None:
                raise OdfError("this file has no styles to add the style of a block to")
            self.styles.insert_into(styles, *self.missing.values())
        if self.missing or setup_changed:
            assert self.styles is not None  # a missing style or a changed setup needed it
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
    rasterise: Rasterise | None = None,
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
    return _Patch(
        original_bytes,
        baseline,
        current,
        track=track_suggestions,
        losses=losses,
        info=info,
        when=when,
        rasterise=rasterise,
    ).run()
