"""Text boxes and shapes on a slide's table in an ods file (E6.31, D1479).

A box is the element every OpenDocument file draws it with (:func:`claudia_odf_io.box_element`: a ``draw:frame`` with
a ``draw:text-box``, a ``draw:rect``, ``draw:ellipse`` or the triangle's ``draw:custom-shape``) in the ``table:shapes``
of the slide's table, placed like a chart or a picture (:func:`.ods_charts.place_of`). Its fill and line are an
automatic graphic style with the look of its style; its words are a paragraph of the named paragraph style called as
the style of the words is, which says what that style says of them (:meth:`.ods_write_looks.OdsLookWriter.words_style`).

Read back (:func:`held_box_of`), a box is what :func:`claudia_odf_io.held_box` makes of an element; its look is what the
file says, for :func:`._boxes.styled` to compare.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from lxml import etree

from claudia_computes import WorkbookModel
from claudia_computes.styles import DEFAULT_STYLE
from claudia_core import SHAPE_LABEL_STYLE
from claudia_odf_io import NS, box_element, held_box, look_of, qname, xml_safe

from ._placed import Placed
from ._read_back import FileObject
from .ods_chart_files import DrawnFrame, drawing_name
from .ods_charts import place_of
from .ods_write_looks import OdsLookWriter


def box_frame(model: WorkbookModel, placed: Placed, styles: OdsLookWriter, name: str) -> etree._Element:
    """The element of the text box or shape ``placed``, called ``name``."""
    body = placed.obj.body
    words = None
    if body.paragraph is not None:
        words = etree.Element(qname("text:p"), nsmap={"text": NS["text"]})
        words.set(qname("text:style-name"), styles.words_style(body.paragraph.style))
        words.text = xml_safe(body.paragraph.text)
    element = box_element(body, styles.box_style(body.kind, look_of(model, body)), name, words)
    element.set(qname("draw:z-index"), str(placed.layer))
    for key, value in place_of(placed, body.rotation).items():
        element.set(qname(key), value)
    return element


def _words_style(_paragraph: etree._Element, shape: str | None) -> str:
    """The style a file's box gives its words: the plain one of its kind; the mark of the slides says the box's own."""
    return DEFAULT_STYLE if shape is None else SHAPE_LABEL_STYLE


def held_box_of(drawn: DrawnFrame, object_id: str, *, graphics: Mapping[str, etree._Element]) -> FileObject | None:
    """The text box or shape the model may hold (on a slide) of a drawing of a file, as ``object_id``; ``graphics``
    are the file's graphic styles."""
    held = held_box(drawn.frame, graphics, _words_style, plain_words=DEFAULT_STYLE)
    if held is None:
        return None
    body, look = held
    assert body.paragraph is not None  # (a box always has its words)
    name = drawing_name(drawn.frame)
    body = replace(body, id=object_id, name=name, paragraph=replace(body.paragraph, id=object_id))
    kind = "object" if etree.QName(drawn.frame).localname == "frame" else "shape"
    return FileObject(drawn.sheet, drawn.row, drawn.col, drawn.corner, body, kind, drawn.order, look=look)
