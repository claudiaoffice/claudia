"""The text boxes and shapes floating over a text, in a docx (D465): written as a drawing of a shape in a run of the
paragraph they hang from, read back as text box and shape objects, and changed in a kept file.

A text box of the model is an *anchored* ``wps:wsp`` that does not wrap the text (the words do not flow around it, as
the model has it), with one paragraph in it; a shape is the same with the outline Word calls ``ellipse`` (a circle),
``rect`` or ``triangle`` and its words centred. Their place is the character of the paragraph the run stands at.

A box of a file comes in when the model can show it as it is (see :mod:`claudia_core.file_boxes`): one paragraph of
plain words in a text box, or in one of those three outlines, not flipped. Its colours and line are not read: the
model gives it the look of its styles, and a file whose box looks otherwise says ``look``. Word writes a box inside
``mc:AlternateContent`` (the drawing for Word 2010 and later, a legacy picture for the older ones): both are read.
"""

from __future__ import annotations

from collections.abc import Container, Mapping
from dataclasses import dataclass
from typing import Any, cast

from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

from claudia_composes import BUILTIN_STYLES, DEFAULT_STYLE, DEFAULT_WRAP_GAP, TextModel
from claudia_core import (
    ASPECT_TOLERANCE,
    MIN_OBJECT_SIZE,
    SHAPE_LABEL_STYLE,
    ObjectBody,
    VisualObject,
    box_body,
)
from claudia_odf_io import BoxLook, LossLog, look_of, xml_safe
from claudia_opc_io import ANGLE, DECORATIVE_URI, PRESET, SHAPE_OF, is_decorative, look_in, outline, solid, turn_of

from ._boxes import all_boxes, shown_words
from ._docx_pictures import (
    _NS,
    EMU,
    PictureWriter,
    _escape,
    _mark_decorative,
    interleave,
    offset_of,
    pixels,
)
from ._docx_styles import WORD_NAMES, WordNames
from ._wrap import (
    docx_frame_open,
    docx_offset_of,
    docx_position,
    docx_set_position,
    docx_set_wrap,
    docx_wrap_element,
    docx_wrap_of,
)

_BOX_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_SPACE = {**_NS, "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape", "mc": _MC}
#: The ids of the object styles of boxes the model has with the name Word shows for their words, for import.
_WORDS_STYLE = {
    **{style.name: style.id for style in BUILTIN_STYLES if style.kind == "paragraph"},
    **{word: ours for ours, word in WORD_NAMES.items()},
}


def _wps(name: str) -> str:
    """The tag of ``wps:name`` (python-docx does not know the namespace of a shape's drawing)."""
    return f"{{{_SPACE['wps']}}}{name}"


def _path(expression: str) -> Any:  # noqa: ANN401
    return etree.XPath(expression, namespaces=_SPACE)


_DRAWINGS = _path("./w:drawing | ./mc:AlternateContent/mc:Choice/w:drawing")
_FRAME = _path("./wp:inline | ./wp:anchor")
_SHAPES = _path(
    "./wp:inline/a:graphic/a:graphicData[@uri='"
    + _BOX_URI
    + "']/wps:wsp | ./wp:anchor/a:graphic/a:graphicData[@uri='"
    + _BOX_URI
    + "']/wps:wsp"
)
_DOC_PR = _path("./wp:docPr")
_TRANSFORM = _path("./wps:spPr/a:xfrm")
_GEOMETRY = _path("./wps:spPr/a:prstGeom/@prst")
_CONTENT = _path("./wps:txbx/w:txbxContent")
_ALL_BOXES = _path(".//wps:wsp")


@dataclass(frozen=True)
class FileBox:
    """A text box or a shape of a file the model holds: where it is, the run that carries it and what the file says."""

    object_id: str
    paragraph: int  # the index of the paragraph among the paragraphs of the document
    offset: int  # the characters of the paragraph before the run
    run: Any  # the ``w:r`` that holds the drawing
    holder: Any  # what the run holds it in: the ``w:drawing`` or the ``mc:AlternateContent`` around it
    drawing: Any  # the ``w:drawing``
    body: ObjectBody
    look: BoxLook
    wrap: str = "over"  # how the text flows round it (D1061) ...
    gap: int = DEFAULT_WRAP_GAP  # ... and how far the words keep from it
    dx: int = 0  # how far off its character it sits, to the right ...
    dy: int = 0  # ... and down (D1067)


def _first(found: list[Any]) -> Any:  # noqa: ANN401
    return found[0] if found else None


def _words_of(content: Any) -> tuple[str, str | None] | None:  # noqa: ANN401
    """``(the words, the name of their style)`` of a ``w:txbxContent`` that holds one paragraph of plain runs; ``None``
    for anything else (more paragraphs, a table, a field)."""
    if len(content) != 1 or content[0].tag != qn("w:p"):
        return None
    paragraph = content[0]
    words: list[str] = []
    for child in paragraph:
        if child.tag == qn("w:pPr"):
            continue
        if child.tag != qn("w:r") or any(each.tag not in (qn("w:rPr"), qn("w:t")) for each in child):
            return None
        words.extend(each.text or "" for each in child if each.tag == qn("w:t"))
    style = paragraph.find(qn("w:pPr") + "/" + qn("w:pStyle"))
    return "".join(words), None if style is None else style.get(qn("w:val"))


def _look_of_file(shape: Any) -> BoxLook:  # noqa: ANN401
    """The fill and the line a ``wps:wsp`` says it has."""
    return BoxLook(*look_in(shape.find(_wps("spPr")), styled=shape.find(_wps("style")) is not None))


def held_box(drawing: Any) -> tuple[str | None, tuple[int, int], int, str, bool, str, str | None, BoxLook] | None:  # noqa: ANN401
    """What the model holds of a ``w:drawing`` that is a text box or a shape: ``(shape, size, rotation, description,
    decorative, words, the name of their style, look)`` (``shape`` is ``None`` for a text box); ``None`` when it is not
    one the model shows as it is."""
    frames, shapes = _FRAME(drawing), _SHAPES(drawing)
    if len(frames) != 1 or len(shapes) != 1 or len(_ALL_BOXES(drawing)) != 1:
        return None
    shape = shapes[0]
    extent = frames[0].find(qn("wp:extent"))
    rotation = turn_of(_first(_TRANSFORM(shape)))
    preset = _first(_GEOMETRY(shape))
    content = _first(_CONTENT(shape))
    if extent is None or rotation is None or content is None or preset not in SHAPE_OF:
        return None
    words = _words_of(content)
    if words is None:
        return None
    look = _look_of_file(shape)
    flagged = shape.find(_wps("cNvSpPr"))
    # a rectangle nobody sees but its words is a text box: Word says so (``txBox``), LibreOffice by drawing it so
    is_box = preset == "rect" and (
        (flagged is not None and flagged.get("txBox") in ("1", "true")) or (look.fill is None and look.line is None)
    )
    size = (pixels(extent.get("cx")), pixels(extent.get("cy")))
    ours = None if is_box else SHAPE_OF[preset]
    if min(size) < MIN_OBJECT_SIZE or (ours == "circle" and abs(size[0] - size[1]) > ASPECT_TOLERANCE):
        return None
    properties = _first(_DOC_PR(frames[0]))
    description = properties.get("descr", "") if properties is not None else ""
    decorative = is_decorative(properties)
    return ours, size, rotation, description, decorative, words[0], words[1], look


def _style_of(name: str | None, shape: str | None) -> str:
    """The style of the words the file's paragraph style ``name`` is: the model's own style of that name, else the
    words' style of the kind of box."""
    found = _WORDS_STYLE.get(name or "")
    return found if found else (DEFAULT_STYLE if shape is None else SHAPE_LABEL_STYLE)


def file_boxes(document: Any) -> list[FileBox]:  # noqa: ANN401
    """The text boxes and shapes of the paragraphs of ``document`` that the model holds, in the order of the file; the
    ``n``-th is the object ``x{n}``. One in a table, a header or a group is not among them."""
    found: list[FileBox] = []
    styles = {style.style_id: style.name for style in document.styles}
    for index, paragraph in enumerate(document.paragraphs):
        for run in paragraph._p.findall(qn("w:r")):
            drawings = _DRAWINGS(run)
            if len(drawings) != 1:
                continue
            held = held_box(drawings[0])
            if held is None:
                continue
            shape, size, rotation, description, decorative, words, style_id, look = held
            object_id = f"x{len(found) + 1}"
            style = _style_of(styles.get(style_id or ""), shape)
            holder = drawings[0] if drawings[0].getparent() is run else drawings[0].getparent().getparent()
            body = box_body(
                object_id,
                size,
                words,
                style,
                shape=shape,
                description=description,
                decorative=decorative,
                rotation=rotation,
            )
            wrap = (*docx_wrap_of(_FRAME(drawings[0])[0]), *docx_offset_of(_FRAME(drawings[0])[0]))
            found.append(
                FileBox(object_id, index, offset_of(paragraph._p, run), run, holder, drawings[0], body, look, *wrap)
            )
    return found


# ------------------------------------------------------------------------------------------------------ writing
class BoxWriter:
    """Writes the text boxes and shapes of a text into a document: the drawing of each, with its words in a paragraph of
    the style the model gives them."""

    def __init__(self, document: Any, names: WordNames, model: TextModel, ids: PictureWriter | None = None) -> None:  # noqa: ANN401
        self.document, self.names, self.model = document, names, model
        self.ids = ids if ids is not None else PictureWriter(document)  # (the pictures' own numbers: no two the same)

    def run(self, obj: VisualObject) -> Any:  # noqa: ANN401
        """The ``w:r`` that carries the drawing of ``obj``."""
        body = obj.body
        width, height = body.w * EMU, body.h * EMU
        number, self.ids.next_id = self.ids.next_id, self.ids.next_id + 1
        title = f"{'Text box' if body.kind == 'text' else 'Shape'} {number}"
        alt = "" if body.decorative else _escape(body.description)
        decorative = (
            f'<a:extLst><a:ext uri="{DECORATIVE_URI}"><adec:decorative xmlns:adec="{_NS["adec"]}" val="1"/></a:ext>'
            "</a:extLst>"
            if body.decorative
            else ""
        )
        turn = f' rot="{body.rotation * ANGLE}"' if body.rotation else ""
        look = look_of(self.model, body)
        fill = solid(look.fill)
        line = outline(look.line, look.width)
        preset = "rect" if body.kind == "text" else PRESET[body.shape or "rectangle"]
        box = ' txBox="1"' if body.kind == "text" else ""
        centre = "ctr" if body.kind == "shape" else "t"
        xml = (
            f'<w:r xmlns:w="{_NS["w"]}" xmlns:wp="{_NS["wp"]}" xmlns:a="{_NS["a"]}" xmlns:r="{_NS["r"]}" '
            f'xmlns:wps="{_SPACE["wps"]}"><w:drawing>'
            f"{docx_frame_open(obj.anchor, number)}"
            '<wp:simplePos x="0" y="0"/>'
            f"{docx_position(obj.anchor)}"
            f'<wp:extent cx="{width}" cy="{height}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f"{docx_wrap_element(obj.anchor)}"
            f'<wp:docPr id="{number}" name="{title}" descr="{alt}">{decorative}</wp:docPr><wp:cNvGraphicFramePr/>'
            f'<a:graphic><a:graphicData uri="{_BOX_URI}"><wps:wsp><wps:cNvSpPr{box}/>'
            f'<wps:spPr><a:xfrm{turn}><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'
            f'<a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>{fill}{line}</wps:spPr>'
            "<wps:txbx><w:txbxContent/></wps:txbx>"
            f'<wps:bodyPr rot="0" vert="horz" wrap="square" anchor="{centre}"><a:noAutofit/></wps:bodyPr>'
            "</wps:wsp></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>"
        )
        run = parse_xml(xml)
        content = _first(_CONTENT(_first(_ALL_BOXES(run))))
        content.append(self.paragraph(body))
        return run

    def paragraph(self, body: ObjectBody) -> Any:  # noqa: ANN401
        """The ``w:p`` of the words of a box, in the Word style the model's style of them is."""
        words = body.paragraph
        text = xml_safe(shown_words(self.model, words)) if words is not None else ""
        element = parse_xml(f'<w:p xmlns:w="{_NS["w"]}"/>')
        if text:
            element.append(parse_xml(f'<w:r xmlns:w="{_NS["w"]}"><w:t xml:space="preserve"/></w:r>'))
            element[0][0].text = text
        if words is not None:
            Paragraph(cast(Any, element), self.document._body).style = self.names.of(words.style)
        return element


# ------------------------------------------------------------------------------------------------------ changing
def _same_but(before: ObjectBody, after: ObjectBody) -> bool:
    """Do ``before`` and ``after`` differ in nothing but what :func:`restyle` can change in place?"""
    return (before.kind, before.shape, before.style) == (after.kind, after.shape, after.style)


def restyle(box: FileBox, before: ObjectBody, after: ObjectBody, document: Any, names: WordNames) -> None:  # noqa: ANN401
    """Give the drawing of ``box`` the description, the decorative mark, the size, the turn and the words of ``after``
    (what changed from ``before``; what did not stays as the file has it)."""
    frame = _FRAME(box.drawing)[0]
    properties = _first(_DOC_PR(frame))
    shape = _first(_SHAPES(box.drawing))
    if (before.description, before.decorative) != (after.description, after.decorative) and properties is not None:
        properties.set("descr", "" if after.decorative else after.description)
        _mark_decorative(properties, after.decorative)
    if (before.w, before.h) != (after.w, after.h):
        cx, cy = str(after.w * EMU), str(after.h * EMU)
        frame.find(qn("wp:extent")).set("cx", cx)
        frame.find(qn("wp:extent")).set("cy", cy)
        transform = _first(_TRANSFORM(shape))
        if transform is not None and (extent := transform.find(qn("a:ext"))) is not None:
            extent.set("cx", cx)
            extent.set("cy", cy)
    if before.rotation != after.rotation and (transform := _first(_TRANSFORM(shape))) is not None:
        if after.rotation:
            transform.set("rot", str(after.rotation * ANGLE))
        elif "rot" in transform.attrib:
            del transform.attrib["rot"]
    if before.paragraph != after.paragraph and after.paragraph is not None:
        _set_words(_first(_CONTENT(shape)), before.paragraph, after.paragraph, document, names)


def _set_words(content: Any, before: Any, after: Any, document: Any, names: WordNames) -> None:  # noqa: ANN401
    """Write the words of ``after`` into the one paragraph of ``content`` (a ``w:txbxContent``), keeping what the
    paragraph has of its own (its properties) unless the words' style changed from ``before``."""
    element = content[0]
    for run in element.findall(qn("w:r")):
        element.remove(run)
    text = xml_safe(after.text)
    if text:
        run = parse_xml(f'<w:r xmlns:w="{_NS["w"]}"><w:t xml:space="preserve"/></w:r>')
        run[0].text = text
        element.append(run)
    if before is None or before.style != after.style:
        Paragraph(element, document._body).style = names.of(after.style)


def restyled_words(baseline: TextModel, current: TextModel) -> set[str]:
    """The styles of words the file needs that it may not have: those of boxes that are new, drawn anew (another outline
    or style) or whose words changed their style."""
    found = set()
    for obj in all_boxes(current).values():
        paragraph = obj.body.paragraph
        if paragraph is None:
            continue
        before = baseline.objects.get(obj.id)
        if (
            before is None
            or not _same_but(before.body, obj.body)
            or before.body.paragraph is None
            or before.body.paragraph.style != paragraph.style
        ):
            found.add(paragraph.style)
    return found


def take_out(box: FileBox) -> None:
    """Take the drawing of ``box`` out of the file; its run too when nothing else is in it."""
    run = box.run
    run.remove(box.holder)
    if not [each for each in run if each.tag != qn("w:rPr")]:
        run.getparent().remove(run)


class BoxEdits:
    """What the text boxes and shapes of a kept file need for the edits from ``baseline`` to ``current``: the drawing
    of one that went is taken out, one that changed gets its words, description, size and turn, one that moved or hangs
    from a paragraph whose words are written again is lifted out to be put back where the text says, one whose outline
    or style changed is drawn anew (it gets the look of its style), and a new one is drawn. ``ids`` is the writer of the
    pictures, whose numbers for the drawings the boxes continue.

    The interface is that of :class:`~claudia_composes_io._docx_pictures.PictureEdits`: ``marks`` are the runs for the
    paragraphs ``rewritten`` (by paragraph id), :meth:`settle` puts the others in place."""

    def __init__(  # noqa: PLR0913
        self,
        document: Any,  # noqa: ANN401
        names: WordNames,
        baseline: TextModel,
        current: TextModel,
        rewritten: Container[str],
        ids: PictureWriter,
        losses: LossLog | None = None,
    ) -> None:
        self.document, self.names, self.rewritten, self.losses = document, names, rewritten, losses
        self.marks: dict[str, list[tuple[int, Any]]] = {}
        self.loose: dict[str, list[tuple[int, Any]]] = {}
        self._writer = BoxWriter(document, names, current, ids)
        wanted = all_boxes(current)
        for box in file_boxes(document):
            self._edit(box, wanted.pop(box.object_id, None), baseline)
        for obj in wanted.values():
            self._route(obj, self._writer.run(obj))

    def _edit(self, box: FileBox, now: VisualObject | None, baseline: TextModel) -> None:
        if now is None:
            take_out(box)
            return
        before = baseline.get_object(box.object_id)
        if not _same_but(before.body, now.body):  # another outline or look: drawn anew where it hangs now
            take_out(box)
            self._route(now, self._writer.run(now))
            if self.losses is not None and not box.look.matches(look_of(baseline, before.body)):
                self.losses.add("look")
            return
        restyle(box, before.body, now.body, self.document, self.names)
        if (now.anchor.wrap, now.anchor.gap) != (before.anchor.wrap, before.anchor.gap):
            docx_set_wrap(_FRAME(box.drawing)[0], now.anchor)
        if (now.anchor.dx, now.anchor.dy) != (before.anchor.dx, before.anchor.dy):
            docx_set_position(_FRAME(box.drawing)[0], now.anchor)
        if now.anchor.paragraph in self.rewritten or now.anchor != before.anchor:
            box.run.getparent().remove(box.run)
            self._route(now, box.run)

    def _route(self, obj: VisualObject, run: Any) -> None:  # noqa: ANN401
        where = self.marks if obj.anchor.paragraph in self.rewritten else self.loose
        where.setdefault(obj.anchor.paragraph, []).append((obj.anchor.offset, run))

    def settle(self, paragraph_of: Mapping[str, Any]) -> None:
        """Put the boxes of the paragraphs that were not written again into them (``paragraph_of``: the ``w:p`` of each
        paragraph id)."""
        for paragraph_id, marks in self.loose.items():
            interleave(paragraph_of[paragraph_id], marks)
